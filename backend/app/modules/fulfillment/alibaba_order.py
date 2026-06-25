"""1688 trade client: order placement (下单) and logistics tracking.

Wraps the 1688 Open Platform trade APIs used to fulfill a 抖店 order:
    - alibaba.trade.fastCreateOrder  (preview + create a cross-border/domestic order)
    - alibaba.trade.createOrder      (create against a confirmed offer)
    - alibaba.trade.getLogisticsTraceInfo (track shipment)

The 1688 param2 gateway uses an MD5 signature over the sorted business
params prefixed by the API path. Trade endpoints additionally require an
OAuth access token. When credentials are not configured the client degrades
gracefully (returns an unconfigured result and logs), mirroring the
behavior of SupplierMatcher so the pipeline never hard-crashes in dev.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CreateOrderResult:
    """Outcome of a 1688 order creation call."""

    success: bool
    alibaba_order_id: str = ""
    total_amount: float = 0.0
    error_message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LogisticsTraceResult:
    """Outcome of a 1688 logistics trace query."""

    success: bool
    tracking_no: str = ""
    logistics_company: str = ""
    status: str = ""
    # Ordered list of {"time": str, "desc": str} events, newest last.
    steps: list[dict[str, str]] = field(default_factory=list)
    error_message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class AlibabaOrderClient:
    """Client for the 1688 trade (order + logistics) APIs.

    Usage:
        client = AlibabaOrderClient(rate_limiter)
        result = await client.create_order(offer_id, quantity=1, receiver=...)
        trace = await client.get_logistics_trace(result.alibaba_order_id)
        await client.close()
    """

    BASE_URL = "https://gw.open.1688.com/openapi"

    def __init__(self, rate_limiter: TokenBucketRateLimiter) -> None:
        self.rate_limiter = rate_limiter
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -------------------------------------------------------------------------
    # Signing
    # -------------------------------------------------------------------------

    def _sign(self, api_path: str, params: dict[str, Any]) -> str:
        """Compute the 1688 param2 MD5 signature.

        Algorithm: sort business params by key, concat as ``k+v`` pairs, prefix
        with the API path (``param2/1/...``), then HMAC-MD5-style digest using
        the app secret as both prefix/suffix wrap, uppercased hex.
        """
        sorted_items = sorted(params.items(), key=lambda kv: kv[0])
        concatenated = "".join(f"{k}{v}" for k, v in sorted_items)
        sign_base = f"{api_path}{concatenated}"
        secret = settings.ALIBABA_1688_APP_SECRET.encode("utf-8")
        digest = hashlib.new(
            "md5", secret + sign_base.encode("utf-8") + secret
        ).hexdigest()
        return digest.upper()

    def _is_configured(self) -> bool:
        return bool(
            settings.ALIBABA_1688_APP_KEY
            and settings.ALIBABA_1688_APP_SECRET
            and settings.ALIBABA_1688_ACCESS_TOKEN
        )

    async def _post(self, api_path: str, biz_params: dict[str, Any]) -> dict[str, Any]:
        """Sign and POST a trade request to the 1688 gateway."""
        params = {
            "access_token": settings.ALIBABA_1688_ACCESS_TOKEN,
            **{k: v for k, v in biz_params.items() if v is not None},
        }
        params["_aop_signature"] = self._sign(api_path, params)

        client = await self._get_client()
        response = await client.post(f"{self.BASE_URL}/{api_path}", data=params)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Order placement
    # -------------------------------------------------------------------------

    async def create_order(
        self,
        offer_id: str,
        quantity: int,
        receiver: dict[str, Any],
        sku_id: str | None = None,
        message: str = "",
    ) -> CreateOrderResult:
        """Place a 1688 order for the given offer to fulfill a 抖店 order.

        Args:
            offer_id: 1688 offer (商品) ID to purchase.
            quantity: Units to buy.
            receiver: Shipping address dict with name/phone/province/city/area/address.
            sku_id: Specific 1688 SKU ID if the offer has variants.
            message: Optional remark to the supplier.

        Returns:
            CreateOrderResult with the upstream order id on success.
        """
        if not self._is_configured():
            logger.warning(
                "1688 trade not configured; skipping create_order for offer=%s", offer_id
            )
            return CreateOrderResult(
                success=False, error_message="1688 trade credentials not configured"
            )

        await self.rate_limiter.acquire("alibaba_1688")

        api_path = "param2/1/com.alibaba.trade/alibaba.trade.fastCreateOrder"
        cargo = {
            "offerId": offer_id,
            "quantity": quantity,
        }
        if sku_id:
            cargo["specId"] = sku_id

        address = {
            "fullName": receiver.get("name", ""),
            "mobile": receiver.get("phone", ""),
            "phone": receiver.get("phone", ""),
            "provinceText": receiver.get("province", ""),
            "cityText": receiver.get("city", ""),
            "areaText": receiver.get("area", ""),
            "address": receiver.get("address", ""),
            "postCode": receiver.get("post_code", ""),
        }

        import json

        biz_params = {
            "flow": "general",
            "message": message,
            "cargoParamList": json.dumps([cargo], ensure_ascii=False),
            "addressParam": json.dumps(address, ensure_ascii=False),
        }

        logger.info(
            "1688 create_order: offer=%s qty=%d",
            offer_id,
            quantity,
            extra={"api_cost": "1688_create_order", "tokens_used": 1},
        )

        try:
            data = await self._post(api_path, biz_params)
        except httpx.HTTPStatusError as e:
            logger.error("1688 create_order HTTP error: status=%d", e.response.status_code)
            return CreateOrderResult(
                success=False, error_message=f"HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error("1688 create_order network error: %s", str(e))
            return CreateOrderResult(success=False, error_message=str(e))

        return self._parse_create_result(data)

    def _parse_create_result(self, data: dict[str, Any]) -> CreateOrderResult:
        """Parse a fastCreateOrder/createOrder response."""
        # Gateway-level error.
        if data.get("error_code") or data.get("errorCode"):
            msg = data.get("error_message") or data.get("errorMessage") or "1688 error"
            return CreateOrderResult(success=False, error_message=str(msg), raw=data)

        result = data.get("result", data)
        # 1688 success flag may be nested or top-level.
        success = bool(result.get("success", True))
        order_id = str(
            result.get("orderId")
            or result.get("order_id")
            or result.get("tradeId", "")
        )
        amount = float(
            result.get("totalSuccessAmount")
            or result.get("sumPayment")
            or result.get("totalAmount")
            or 0.0
        )

        if not success or not order_id:
            return CreateOrderResult(
                success=False,
                error_message=str(result.get("errorMessage", "create order failed")),
                raw=data,
            )

        return CreateOrderResult(
            success=True,
            alibaba_order_id=order_id,
            total_amount=amount,
            raw=data,
        )

    # -------------------------------------------------------------------------
    # Logistics tracking
    # -------------------------------------------------------------------------

    async def get_logistics_trace(self, alibaba_order_id: str) -> LogisticsTraceResult:
        """Fetch the logistics trace for a 1688 order.

        Args:
            alibaba_order_id: The 1688 order id returned from create_order.

        Returns:
            LogisticsTraceResult with company / tracking no / ordered steps.
        """
        if not self._is_configured():
            logger.warning(
                "1688 trade not configured; skipping logistics trace for order=%s",
                alibaba_order_id,
            )
            return LogisticsTraceResult(
                success=False, error_message="1688 trade credentials not configured"
            )

        await self.rate_limiter.acquire("alibaba_1688")

        api_path = (
            "param2/1/com.alibaba.logistics/alibaba.trade.getLogisticsTraceInfo"
        )
        biz_params = {
            "orderId": alibaba_order_id,
            "webSite": "1688",
        }

        logger.info(
            "1688 logistics trace: order=%s",
            alibaba_order_id,
            extra={"api_cost": "1688_logistics_trace", "tokens_used": 1},
        )

        try:
            data = await self._post(api_path, biz_params)
        except httpx.HTTPStatusError as e:
            logger.error("1688 logistics HTTP error: status=%d", e.response.status_code)
            return LogisticsTraceResult(
                success=False, error_message=f"HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error("1688 logistics network error: %s", str(e))
            return LogisticsTraceResult(success=False, error_message=str(e))

        return self._parse_trace_result(data)

    def _parse_trace_result(self, data: dict[str, Any]) -> LogisticsTraceResult:
        """Parse a getLogisticsTraceInfo response."""
        if data.get("error_code") or data.get("errorCode"):
            msg = data.get("error_message") or data.get("errorMessage") or "1688 error"
            return LogisticsTraceResult(success=False, error_message=str(msg), raw=data)

        result = data.get("result", data)
        # Trace info may be a list of logistics groups; take the first.
        trace_list = result.get("logisticsTrace") or result.get("traceList") or []
        if isinstance(trace_list, dict):
            trace_list = [trace_list]

        if not trace_list:
            return LogisticsTraceResult(success=True, status="no_trace", raw=data)

        first = trace_list[0]
        steps_raw = first.get("logisticsSteps") or first.get("steps") or []
        steps = [
            {
                "time": str(s.get("acceptTime") or s.get("time", "")),
                "desc": str(s.get("remark") or s.get("desc", "")),
            }
            for s in steps_raw
        ]

        return LogisticsTraceResult(
            success=True,
            tracking_no=str(first.get("mailNo") or first.get("trackingNo", "")),
            logistics_company=str(
                first.get("logisticsCompanyName") or first.get("company", "")
            ),
            status=str(first.get("status") or ("delivered" if steps else "shipped")),
            steps=steps,
            raw=data,
        )
