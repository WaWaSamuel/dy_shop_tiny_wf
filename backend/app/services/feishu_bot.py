"""Feishu IM bot service based on long connection mode."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import ReadSession, WriteSession
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)

PENDING_CONFIRMATION_TTL_SECONDS = 30 * 60


@dataclass
class FeishuBotStatus:
    """Public bot runtime status."""

    enabled: bool
    configured: bool
    running: bool
    target_open_id: str = ""
    default_chat_id: str = ""
    owner_id: str = ""


@dataclass
class FeishuBotReply:
    """Single outgoing bot reply."""

    msg_type: str
    content: str


class FeishuBotService:
    """Feishu long-connection bot with card-based replies."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._api_client: Any = None
        self._ws_client: Any = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._sdk: Any = None

    @property
    def enabled(self) -> bool:
        return self.settings.FEISHU_BOT_ENABLED

    @property
    def configured(self) -> bool:
        return bool(self.settings.FEISHU_APP_ID and self.settings.FEISHU_APP_SECRET)

    @property
    def ready(self) -> bool:
        return self.enabled and self.configured and self._running and self._api_client is not None

    def status(self) -> FeishuBotStatus:
        return FeishuBotStatus(
            enabled=self.enabled,
            configured=self.configured,
            running=self._running,
            target_open_id=self.settings.FEISHU_BOT_TARGET_OPEN_ID,
            default_chat_id=self.settings.FEISHU_BOT_DEFAULT_CHAT_ID,
            owner_id=self.settings.FEISHU_BOT_OWNER_ID,
        )

    async def start(self) -> None:
        """Initialize Feishu API client and start websocket listener thread."""
        self._main_loop = asyncio.get_running_loop()

        if not self.enabled:
            logger.info("Feishu bot disabled. Skip startup.")
            return
        if not self.configured:
            logger.warning("Feishu bot enabled but app credentials are missing.")
            return

        try:
            lark = self._load_sdk()
        except ImportError:
            logger.exception("Feishu bot SDK is unavailable.")
            return

        self._sdk = lark
        self._api_client = (
            lark.Client.builder()
            .app_id(self.settings.FEISHU_APP_ID)
            .app_secret(self.settings.FEISHU_APP_SECRET)
            .domain(self.settings.FEISHU_BASE_DOMAIN)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

        self._ws_thread = threading.Thread(
            target=self._run_ws_client,
            name="feishu-bot-ws",
            daemon=True,
        )
        self._ws_thread.start()
        self._running = True
        logger.info("Feishu bot websocket thread started.")

    async def stop(self) -> None:
        """Mark service stopped."""
        self._running = False
        logger.info("Feishu bot marked as stopped.")

    def _load_sdk(self) -> Any:
        import lark_oapi as lark

        return lark

    def _run_ws_client(self) -> None:
        try:
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            import lark_oapi.ws.client as ws_client_module

            ws_client_module.loop = thread_loop

            event_handler = (
                self._sdk.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(self._on_message_event)
                .build()
            )

            self._ws_client = self._sdk.ws.Client(
                self.settings.FEISHU_APP_ID,
                self.settings.FEISHU_APP_SECRET,
                event_handler=event_handler,
                domain=self.settings.FEISHU_BASE_DOMAIN,
                log_level=self._sdk.LogLevel.INFO,
            )
            self._ws_client.start()
        except Exception:
            logger.exception("Feishu websocket client exited unexpectedly.")
            self._running = False

    def _on_message_event(self, data: Any) -> None:
        if self._main_loop is None or self._main_loop.is_closed():
            logger.warning("Main event loop unavailable. Skip Feishu event.")
            return

        future = asyncio.run_coroutine_threadsafe(
            self._handle_message_event(data),
            self._main_loop,
        )
        future.add_done_callback(self._log_future_error)

    @staticmethod
    def _log_future_error(future: asyncio.Future[Any]) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Feishu event task failed.")

    async def _handle_message_event(self, data: Any) -> None:
        if not data or not getattr(data, "event", None) or not getattr(data.event, "message", None):
            return

        logger.info("Feishu incoming event:\n%s", self._serialize_event(data))

        message = data.event.message
        sender = getattr(data.event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)
        sender_open_id = getattr(sender_id, "open_id", None)

        message_id = getattr(message, "message_id", None)
        chat_id = getattr(message, "chat_id", None)
        chat_type = getattr(message, "chat_type", None) or ""
        message_type = getattr(message, "message_type", None) or ""
        raw_content = getattr(message, "content", None) or ""

        if not message_id or not chat_id:
            return

        if message_type != "text":
            await self.reply_message(
                message_id=message_id,
                reply=self.build_info_card(
                    title="暂不支持的消息类型",
                    lines=[
                        "当前机器人只接收文本指令。",
                        "发送 `帮助` 查看可用命令。",
                    ],
                    template="orange",
                ),
            )
            return

        text_content = self._extract_text_content(raw_content)
        if not text_content:
            await self.reply_message(
                message_id=message_id,
                reply=self.build_info_card(
                    title="未解析到文本",
                    lines=[
                        "消息里没有提取到可识别的文本内容。",
                        "发送 `帮助` 查看可用命令。",
                    ],
                    template="orange",
                ),
            )
            return

        reply = await self._dispatch_command(
            text_content=text_content,
            chat_id=chat_id,
            chat_type=chat_type,
            sender_open_id=sender_open_id,
        )
        if reply:
            await self.reply_message(message_id=message_id, reply=reply)

    @staticmethod
    def _extract_text_content(raw_content: str) -> str:
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            return raw_content.strip()
        text_value = payload.get("text", "")
        return " ".join(str(text_value).strip().split())

    def _serialize_event(self, data: Any) -> str:
        if self._sdk is not None and hasattr(self._sdk, "JSON"):
            try:
                return self._sdk.JSON.marshal(data, indent=2)
            except Exception:
                logger.exception("Failed to serialize Feishu event with SDK JSON helper.")

        try:
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(data)

    async def _dispatch_command(
        self,
        *,
        text_content: str,
        chat_id: str,
        chat_type: str,
        sender_open_id: Optional[str],
    ) -> FeishuBotReply:
        normalized = text_content.strip()
        lowered = normalized.lower()

        if normalized in {"确认", "取消"}:
            return await self.handle_pending_confirmation(
                decision=normalized,
                chat_id=chat_id,
                sender_open_id=sender_open_id,
            )

        if normalized == "你好":
            return self.build_info_card(
                title="你好",
                lines=["我是小八呀"],
                template="blue",
            )

        if lowered in {"帮助", "help", "/help", "菜单"}:
            return self.help_card()

        if normalized.startswith("订单列表"):
            status_filter = normalized.removeprefix("订单列表").strip() or None
            return await self.list_orders(status_filter)

        if normalized.startswith("确认订单"):
            order_ref = normalized.removeprefix("确认订单").strip()
            if not order_ref:
                return self.build_info_card(
                    title="命令格式不正确",
                    lines=["用法：`确认订单 <订单ID>`"],
                    template="orange",
                )
            return await self.push_order_confirmation(
                order_ref=order_ref,
                chat_id=chat_id,
                sender_open_id=sender_open_id,
                reply_mode=True,
            )

        if normalized.startswith("推送新闻"):
            payload = normalized.removeprefix("推送新闻").strip()
            return await self.handle_news_push(payload, current_chat_id=chat_id, chat_type=chat_type)

        return self.build_info_card(
            title="未识别的指令",
            lines=[
                f"收到的文本：`{normalized}`",
                "发送 `帮助` 查看支持的命令。",
            ],
            template="grey",
        )

    def help_card(self) -> FeishuBotReply:
        return self.build_info_card(
            title="飞书机器人命令",
            lines=[
                "1. `帮助`",
                "2. `订单列表 [状态]`",
                "3. `确认订单 <订单ID>`",
                "4. `推送新闻 <标题> | <链接> | <摘要>`",
                "",
                "推送优先发给 `FEISHU_BOT_TARGET_OPEN_ID`，否则回退到默认群或当前会话。",
                "订单类命令仍然读取 `FEISHU_BOT_OWNER_ID` 对应的业务数据。",
            ],
            template="blue",
        )

    def build_info_card(
        self,
        *,
        title: str,
        lines: list[str],
        template: str = "blue",
    ) -> FeishuBotReply:
        content = "\n".join(lines).strip()
        return self.build_markdown_card(title=title, markdown_blocks=[content], template=template)

    def build_markdown_card(
        self,
        *,
        title: str,
        markdown_blocks: list[str],
        template: str = "blue",
    ) -> FeishuBotReply:
        elements: list[dict[str, Any]] = []
        has_content = False
        for block in markdown_blocks:
            if not block.strip():
                continue
            if has_content:
                elements.append({"tag": "hr"})
            elements.append({"tag": "markdown", "content": block})
            has_content = True

        card = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": template,
            },
            "elements": elements,
        }
        return FeishuBotReply(
            msg_type="interactive",
            content=json.dumps(card, ensure_ascii=False),
        )

    async def list_orders(self, status_filter: Optional[str] = None) -> FeishuBotReply:
        owner_id = self.settings.FEISHU_BOT_OWNER_ID
        if not owner_id:
            return self.build_info_card(
                title="订单查询不可用",
                lines=["未配置 `FEISHU_BOT_OWNER_ID`，当前无法查询订单。"],
                template="orange",
            )

        conditions = ["owner_id = :owner_id"]
        params: dict[str, Any] = {"owner_id": owner_id}
        if status_filter:
            conditions.append("status = :status")
            params["status"] = status_filter

        query = text(
            f"""
            SELECT id, status, total_amount, channel, created_at
            FROM orders
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT 5
            """
        )

        async with ReadSession() as session:
            rows = (await session.execute(query, params)).mappings().all()

        if not rows:
            suffix = f"（状态：{status_filter}）" if status_filter else ""
            return self.build_info_card(
                title="最近订单",
                lines=[f"最近没有查到订单{suffix}。"],
                template="grey",
            )

        blocks = [
            f"最近 5 条订单{'（' + status_filter + '）' if status_filter else ''}",
            "\n".join(
                [
                    f"**{index + 1}.** `{row['id']}`\n"
                    f"状态：`{row['status']}`  ｜ 渠道：`{row['channel']}`  ｜ 金额：`${float(row['total_amount']):.2f}`"
                    for index, row in enumerate(rows)
                ]
            ),
        ]
        return self.build_markdown_card(title="订单列表", markdown_blocks=blocks, template="indigo")

    async def push_order_confirmation(
        self,
        *,
        order_ref: str,
        chat_id: Optional[str] = None,
        sender_open_id: Optional[str] = None,
        open_id: Optional[str] = None,
        reply_mode: bool = False,
    ) -> FeishuBotReply:
        owner_id = self.settings.FEISHU_BOT_OWNER_ID
        if reply_mode and not owner_id:
            return self.build_info_card(
                title="订单确认不可用",
                lines=["未配置 `FEISHU_BOT_OWNER_ID`，当前无法发送订单确认卡片。"],
                template="orange",
            )

        order_row = await self.fetch_order_detail(order_ref=order_ref, owner_id=owner_id or None)
        if not order_row:
            if not reply_mode:
                raise ValueError(f"未找到订单：{order_ref}")
            return self.build_info_card(
                title="订单不存在",
                lines=[f"未找到订单：`{order_ref}`"],
                template="orange",
            )

        current_status = str(order_row["status"])
        if current_status in {"cancelled", "refunded", "delivered"}:
            if not reply_mode:
                raise ValueError(f"订单 {order_row['id']} 当前状态为 {current_status}，不适合再确认。")
            return self.build_info_card(
                title="订单状态不可确认",
                lines=[
                    f"订单：`{order_row['id']}`",
                    f"当前状态：`{current_status}`",
                    "这个状态不适合再走确认流程。",
                ],
                template="grey",
            )

        reply = self.build_order_confirmation_card(order_row)
        target_open_id = open_id or sender_open_id or self.settings.FEISHU_BOT_TARGET_OPEN_ID
        if not reply_mode:
            receive_id_type, receive_id, _ = self.resolve_push_target(
                open_id=open_id,
                chat_id=chat_id,
            )
            await self.send_message(
                receive_id_type=receive_id_type,
                receive_id=receive_id,
                reply=reply,
            )
        await self.store_pending_confirmation(
            chat_id=chat_id or "",
            sender_open_id=target_open_id,
            payload={
                "type": "order_confirmation",
                "order_id": str(order_row["id"]),
                "owner_id": str(order_row["owner_id"]),
            },
        )
        return reply

    async def handle_pending_confirmation(
        self,
        *,
        decision: str,
        chat_id: str,
        sender_open_id: Optional[str],
    ) -> FeishuBotReply:
        pending = await self.get_pending_confirmation(chat_id=chat_id, sender_open_id=sender_open_id)
        if not pending:
            return self.build_info_card(
                title="没有待处理确认",
                lines=["当前会话没有待确认的订单卡片。"],
                template="grey",
            )

        if pending.get("type") != "order_confirmation":
            await self.clear_pending_confirmation(chat_id=chat_id, sender_open_id=sender_open_id)
            return self.build_info_card(
                title="待处理数据已失效",
                lines=["上下文已失效，请重新发送确认请求。"],
                template="grey",
            )

        owner_id = str(pending.get("owner_id") or "")
        order_id = str(pending.get("order_id") or "")
        if not owner_id or not order_id:
            await self.clear_pending_confirmation(chat_id=chat_id, sender_open_id=sender_open_id)
            return self.build_info_card(
                title="待确认数据不完整",
                lines=["上下文缺少订单信息，请重新发起确认流程。"],
                template="orange",
            )

        final_status = "confirmed" if decision == "确认" else "cancelled"
        result = await self.apply_order_decision(
            order_id=order_id,
            owner_id=owner_id,
            final_status=final_status,
        )
        await self.clear_pending_confirmation(chat_id=chat_id, sender_open_id=sender_open_id)

        if not result:
            return self.build_info_card(
                title="订单不存在",
                lines=[f"未找到订单：`{order_id}`"],
                template="orange",
            )

        if result["ok"]:
            result_order = result["order"]
            return self.build_info_card(
                title="订单处理完成",
                lines=[
                    f"订单：`{result_order['id']}`",
                    f"当前状态：`{result_order['status']}`",
                    f"金额：`${float(result_order['total_amount']):.2f}`",
                    f"操作结果：已{'确认' if final_status == 'confirmed' else '取消'}。",
                ],
                template="green" if final_status == "confirmed" else "red",
            )

        return self.build_info_card(
            title="订单状态未变更",
            lines=result["lines"],
            template="orange",
        )

    async def handle_news_push(
        self,
        payload: str,
        *,
        current_chat_id: str,
        chat_type: str,
    ) -> FeishuBotReply:
        if not payload:
            return self.build_info_card(
                title="命令格式不正确",
                lines=["用法：`推送新闻 <标题> | <链接> | <摘要>`"],
                template="orange",
            )

        segments = [segment.strip() for segment in payload.split("|")]
        if len(segments) < 2:
            return self.build_info_card(
                title="命令格式不正确",
                lines=["用法：`推送新闻 <标题> | <链接> | <摘要>`"],
                template="orange",
            )

        title = segments[0]
        url = segments[1]
        summary = segments[2] if len(segments) > 2 else ""

        _, _, target_hint = self.resolve_push_target(
            open_id=None,
            chat_id=current_chat_id,
            prefer_current_chat=chat_type != "p2p",
        )

        result = await self.push_news(
            title="新闻热点推送",
            content="来自机器人命令的即时推送",
            items=[{"title": title, "url": url, "summary": summary}],
            chat_id=current_chat_id,
        )
        return self.build_info_card(
            title="新闻卡片已发送",
            lines=[
                f"目标：{target_hint}",
                f"消息 ID：`{result.get('message_id') or 'unknown'}`",
            ],
            template="green",
        )

    async def push_news(
        self,
        *,
        title: str,
        content: Optional[str] = None,
        items: Optional[list[dict[str, str]]] = None,
        open_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> dict[str, Any]:
        receive_id_type, receive_id, target_hint = self.resolve_push_target(
            open_id=open_id,
            chat_id=chat_id,
        )

        reply = self.build_news_card(title=title, content=content, items=items or [])
        response = await self.send_message(
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            reply=reply,
        )
        return {
            "receive_id_type": receive_id_type,
            "receive_id": receive_id,
            "target_hint": target_hint,
            "message_id": getattr(getattr(response, "data", None), "message_id", None),
        }

    def build_news_card(
        self,
        *,
        title: str,
        content: Optional[str],
        items: list[dict[str, str]],
    ) -> FeishuBotReply:
        blocks: list[str] = []
        if content:
            blocks.append(content)

        if items:
            for index, item in enumerate(items, start=1):
                item_title = item.get("title", "").strip()
                item_url = item.get("url", "").strip()
                item_summary = item.get("summary", "").strip()
                headline = f"**{index}. [{item_title}]({item_url})**" if item_url else f"**{index}. {item_title}**"
                block = headline
                if item_summary:
                    block += f"\n{item_summary}"
                blocks.append(block)
        else:
            blocks.append("当前没有新闻条目。")

        return self.build_markdown_card(title=title, markdown_blocks=blocks, template="blue")

    def build_order_confirmation_card(self, order_row: dict[str, Any]) -> FeishuBotReply:
        items = order_row.get("items") or []
        item_lines = []
        for index, item in enumerate(items, start=1):
            variant = item.get("variant") or "-"
            item_lines.append(
                f"**{index}.** 商品 `{item.get('product_id')}`\n"
                f"数量：`{item.get('quantity')}` ｜ 单价：`${float(item.get('unit_price') or 0):.2f}` ｜ 规格：`{variant}`"
            )

        item_block = "\n\n".join(item_lines) if item_lines else "当前订单没有商品明细。"
        buyer_notes = order_row.get("notes") or "-"
        shipping_address = order_row.get("shipping_address") or "-"
        tracking_number = order_row.get("tracking_number") or "-"

        return self.build_markdown_card(
            title="订单确认待处理",
            markdown_blocks=[
                (
                    f"**订单 ID**：`{order_row['id']}`\n"
                    f"**状态**：`{order_row['status']}`\n"
                    f"**渠道**：`{order_row['channel']}`\n"
                    f"**金额**：`${float(order_row['total_amount']):.2f}`\n"
                    f"**创建时间**：`{order_row['created_at']}`"
                ),
                (
                    f"**收货地址**：{shipping_address}\n"
                    f"**物流单号**：`{tracking_number}`\n"
                    f"**备注**：{buyer_notes}"
                ),
                item_block,
                "请直接回复 **确认** 或 **取消** 完成这笔订单的处理。",
            ],
            template="orange",
        )

    async def fetch_order_detail(self, *, order_ref: str, owner_id: Optional[str]) -> Optional[dict[str, Any]]:
        where_clause = "CAST(o.id AS TEXT) = :order_ref"
        params: dict[str, Any] = {"order_ref": order_ref}
        if owner_id:
            where_clause += " AND o.owner_id = :owner_id"
            params["owner_id"] = owner_id

        query = text(
            f"""
            SELECT
                o.id,
                o.owner_id,
                o.status,
                o.channel,
                o.total_amount,
                o.shipping_address,
                o.tracking_number,
                o.notes,
                o.created_at,
                o.updated_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'product_id', oi.product_id,
                            'quantity', oi.quantity,
                            'unit_price', oi.unit_price,
                            'variant', oi.variant
                        )
                    ) FILTER (WHERE oi.id IS NOT NULL),
                    '[]'
                ) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE {where_clause}
            GROUP BY o.id
            LIMIT 1
            """
        )
        async with ReadSession() as session:
            row = (
                await session.execute(
                    query,
                    params,
                )
            ).mappings().first()
        return dict(row) if row else None

    async def apply_order_decision(
        self,
        *,
        order_id: str,
        owner_id: str,
        final_status: str,
    ) -> Optional[dict[str, Any]]:
        async with WriteSession() as session:
            lookup_query = text(
                """
                SELECT id, status, total_amount
                FROM orders
                WHERE id = :id AND owner_id = :owner_id
                LIMIT 1
                """
            )
            order_row = (
                await session.execute(
                    lookup_query,
                    {"id": order_id, "owner_id": owner_id},
                )
            ).mappings().first()

            if not order_row:
                return None

            current_status = str(order_row["status"])
            if current_status == final_status:
                return {
                    "ok": False,
                    "lines": [
                        f"订单：`{order_id}`",
                        f"当前状态已经是 `'{current_status}'`。",
                    ],
                }

            if current_status in {"delivered", "refunded"}:
                return {
                    "ok": False,
                    "lines": [
                        f"订单：`{order_id}`",
                        f"当前状态：`{current_status}`",
                        "这个状态不适合再变更。",
                    ],
                }

            update_query = text(
                """
                UPDATE orders
                SET status = :final_status, updated_at = NOW()
                WHERE id = :id AND owner_id = :owner_id
                RETURNING id, status, total_amount
                """
            )
            updated_row = (
                await session.execute(
                    update_query,
                    {
                        "id": order_id,
                        "owner_id": owner_id,
                        "final_status": final_status,
                    },
                )
            ).mappings().first()
            await session.commit()

        return {"ok": True, "order": dict(updated_row)}

    async def store_pending_confirmation(
        self,
        *,
        chat_id: str,
        sender_open_id: Optional[str],
        payload: dict[str, Any],
    ) -> None:
        redis = await get_redis_pool()
        keys = self.pending_confirmation_keys(chat_id=chat_id, sender_open_id=sender_open_id)
        serialized = json.dumps(payload, ensure_ascii=False)
        for key in keys:
            await redis.set(key, serialized, ex=PENDING_CONFIRMATION_TTL_SECONDS)

    async def get_pending_confirmation(
        self,
        *,
        chat_id: str,
        sender_open_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        redis = await get_redis_pool()
        for key in self.pending_confirmation_keys(chat_id=chat_id, sender_open_id=sender_open_id):
            raw_value = await redis.get(key)
            if raw_value:
                return json.loads(raw_value)
        return None

    async def clear_pending_confirmation(
        self,
        *,
        chat_id: str,
        sender_open_id: Optional[str],
    ) -> None:
        redis = await get_redis_pool()
        keys = self.pending_confirmation_keys(chat_id=chat_id, sender_open_id=sender_open_id)
        if keys:
            await redis.delete(*keys)

    @staticmethod
    def pending_confirmation_keys(chat_id: str, sender_open_id: Optional[str]) -> list[str]:
        open_part = sender_open_id or "anonymous"
        keys = [f"feishu:pending_confirmation:{chat_id or 'global'}:{open_part}"]
        if sender_open_id:
            keys.append(f"feishu:pending_confirmation:global:{sender_open_id}")
        return list(dict.fromkeys(keys))

    def resolve_push_target(
        self,
        *,
        open_id: Optional[str],
        chat_id: Optional[str],
        prefer_current_chat: bool = False,
    ) -> tuple[str, str, str]:
        if open_id:
            return "open_id", open_id, "指定飞书用户"
        if self.settings.FEISHU_BOT_TARGET_OPEN_ID:
            return "open_id", self.settings.FEISHU_BOT_TARGET_OPEN_ID, "默认飞书用户"
        if self.settings.FEISHU_BOT_DEFAULT_CHAT_ID and not prefer_current_chat:
            return "chat_id", self.settings.FEISHU_BOT_DEFAULT_CHAT_ID, "默认群聊"
        if chat_id:
            return "chat_id", chat_id, "当前会话"
        if self.settings.FEISHU_BOT_DEFAULT_CHAT_ID:
            return "chat_id", self.settings.FEISHU_BOT_DEFAULT_CHAT_ID, "默认群聊"
        raise ValueError("Missing target open_id/chat_id for Feishu push.")

    async def reply_message(
        self,
        *,
        message_id: str,
        reply: FeishuBotReply,
    ) -> Any:
        if not self._api_client:
            raise RuntimeError("Feishu API client is not initialized.")

        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type(reply.msg_type)
                .content(reply.content)
                .uuid(str(uuid4()))
                .build()
            )
            .build()
        )
        response = await self._api_client.im.v1.message.areply(request)
        if not response.success():
            logger.error(
                "Feishu reply failed, code=%s msg=%s",
                response.code,
                response.msg,
            )
            raise RuntimeError(f"Feishu reply failed: {response.code} {response.msg}")
        return response

    async def send_message(
        self,
        *,
        receive_id_type: str,
        receive_id: str,
        reply: FeishuBotReply,
    ) -> Any:
        if not self._api_client:
            raise RuntimeError("Feishu API client is not initialized.")

        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(reply.msg_type)
                .content(reply.content)
                .uuid(str(uuid4()))
                .build()
            )
            .build()
        )
        response = await self._api_client.im.v1.message.acreate(request)
        if not response.success():
            logger.error(
                "Feishu send message failed, code=%s msg=%s receive_id_type=%s receive_id=%s",
                response.code,
                response.msg,
                receive_id_type,
                receive_id,
            )
            raise RuntimeError(f"Feishu send failed: {response.code} {response.msg}")
        return response


_feishu_bot_service = FeishuBotService()


def get_feishu_bot_service() -> FeishuBotService:
    """Return singleton Feishu bot service."""
    return _feishu_bot_service
