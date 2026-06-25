"""Notification service - WeChat push notifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    WECHAT_WORK = "wechat_work"
    WECHAT_MP = "wechat_mp"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationMessage:
    """A notification message to be sent."""

    title: str
    body: str
    channel: NotificationChannel = NotificationChannel.WECHAT_WORK
    priority: NotificationPriority = NotificationPriority.NORMAL
    recipient_id: str = ""
    recipient_type: str = "user"  # user, group, broadcast
    template_id: Optional[str] = None
    template_data: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    # For deduplication
    idempotency_key: Optional[str] = None


@dataclass
class NotificationResult:
    """Result of sending a notification."""

    success: bool
    message_id: Optional[str] = None
    channel: Optional[NotificationChannel] = None
    error: Optional[str] = None
    response_data: dict[str, Any] = field(default_factory=dict)


class WeChatWorkConfig:
    """WeChat Work (Enterprise WeChat) configuration."""

    def __init__(
        self,
        *,
        corp_id: str = "",
        corp_secret: str = "",
        agent_id: str = "",
        webhook_url: str = "",
        webhook_key: str = "",
    ):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self.webhook_url = webhook_url
        self.webhook_key = webhook_key
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0


class NotificationService:
    """Service for sending notifications via WeChat and other channels.

    Primary channel: WeChat Work (Enterprise WeChat) for business notifications.
    Supports both webhook-based and API-based message delivery.
    """

    def __init__(
        self,
        wechat_config: Optional[WeChatWorkConfig] = None,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.wechat_config = wechat_config or WeChatWorkConfig()
        self._http = http_client
        self._sent_keys: set[str] = set()  # Simple dedup cache

    @property
    def http(self) -> httpx.AsyncClient:
        """Lazy-initialize HTTP client."""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """Send a notification through the specified channel.

        Args:
            message: The notification message to send.

        Returns:
            NotificationResult with delivery status.
        """
        # Deduplication check
        if message.idempotency_key:
            if message.idempotency_key in self._sent_keys:
                logger.info(
                    f"Duplicate notification skipped: {message.idempotency_key}"
                )
                return NotificationResult(
                    success=True,
                    channel=message.channel,
                    error="duplicate_skipped",
                )
            self._sent_keys.add(message.idempotency_key)

        # Route to channel handler
        if message.channel == NotificationChannel.WECHAT_WORK:
            return await self._send_wechat_work(message)
        elif message.channel == NotificationChannel.WECHAT_MP:
            return await self._send_wechat_mp(message)
        elif message.channel == NotificationChannel.IN_APP:
            return await self._send_in_app(message)
        else:
            return NotificationResult(
                success=False,
                channel=message.channel,
                error=f"Channel {message.channel.value} not implemented",
            )

    async def send_batch(
        self, messages: list[NotificationMessage]
    ) -> list[NotificationResult]:
        """Send multiple notifications.

        Args:
            messages: List of messages to send.

        Returns:
            List of results in the same order.
        """
        results: list[NotificationResult] = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    async def _send_wechat_work(
        self, message: NotificationMessage
    ) -> NotificationResult:
        """Send notification via WeChat Work.

        Supports two modes:
        1. Webhook: Simple, no auth needed. Good for group notifications.
        2. API: Full featured, requires access token. For targeted messages.
        """
        if self.wechat_config.webhook_url:
            return await self._send_via_webhook(message)
        else:
            return await self._send_via_api(message)

    async def _send_via_webhook(
        self, message: NotificationMessage
    ) -> NotificationResult:
        """Send via WeChat Work webhook (group bot)."""
        webhook_url = self.wechat_config.webhook_url

        # Build webhook payload
        payload: dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "content": self._format_markdown(message),
            },
        }

        # Add signing if webhook key is configured
        if self.wechat_config.webhook_key:
            timestamp = str(int(time.time()))
            sign = self._generate_sign(timestamp, self.wechat_config.webhook_key)
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        try:
            response = await self.http.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            data = response.json()

            if data.get("errcode") == 0:
                return NotificationResult(
                    success=True,
                    channel=NotificationChannel.WECHAT_WORK,
                    response_data=data,
                )
            else:
                return NotificationResult(
                    success=False,
                    channel=NotificationChannel.WECHAT_WORK,
                    error=data.get("errmsg", "Unknown error"),
                    response_data=data,
                )
        except Exception as e:
            logger.error(f"WeChat webhook send failed: {e}")
            return NotificationResult(
                success=False,
                channel=NotificationChannel.WECHAT_WORK,
                error=str(e),
            )

    async def _send_via_api(
        self, message: NotificationMessage
    ) -> NotificationResult:
        """Send via WeChat Work Message API (requires access token)."""
        access_token = await self._get_access_token()
        if not access_token:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.WECHAT_WORK,
                error="Failed to obtain access token",
            )

        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
            f"?access_token={access_token}"
        )

        payload: dict[str, Any] = {
            "touser": message.recipient_id,
            "msgtype": "text",
            "agentid": self.wechat_config.agent_id,
            "text": {
                "content": f"{message.title}\n\n{message.body}",
            },
        }

        # Use template card if template is specified
        if message.template_id:
            payload["msgtype"] = "template_card"
            payload["template_card"] = {
                "card_type": "text_notice",
                "main_title": {"title": message.title},
                "sub_title_text": message.body,
                "card_action": {
                    "type": 1,
                    "url": message.extra.get("action_url", ""),
                },
            }
            del payload["text"]

        try:
            response = await self.http.post(url, json=payload)
            data = response.json()

            if data.get("errcode") == 0:
                return NotificationResult(
                    success=True,
                    message_id=data.get("msgid"),
                    channel=NotificationChannel.WECHAT_WORK,
                    response_data=data,
                )
            else:
                return NotificationResult(
                    success=False,
                    channel=NotificationChannel.WECHAT_WORK,
                    error=data.get("errmsg", "Unknown error"),
                    response_data=data,
                )
        except Exception as e:
            logger.error(f"WeChat API send failed: {e}")
            return NotificationResult(
                success=False,
                channel=NotificationChannel.WECHAT_WORK,
                error=str(e),
            )

    async def _send_wechat_mp(
        self, message: NotificationMessage
    ) -> NotificationResult:
        """Send via WeChat Mini Program template message."""
        # TODO: Implement WeChat Mini Program template message
        logger.warning("WeChat MP notifications not yet implemented")
        return NotificationResult(
            success=False,
            channel=NotificationChannel.WECHAT_MP,
            error="Not implemented",
        )

    async def _send_in_app(
        self, message: NotificationMessage
    ) -> NotificationResult:
        """Store notification for in-app display."""
        # TODO: Store in database for in-app notification center
        logger.info(
            f"In-app notification: [{message.title}] {message.body} -> {message.recipient_id}"
        )
        return NotificationResult(
            success=True,
            channel=NotificationChannel.IN_APP,
        )

    async def _get_access_token(self) -> Optional[str]:
        """Get or refresh WeChat Work access token."""
        config = self.wechat_config

        # Return cached token if still valid
        if config._access_token and time.time() < config._token_expires_at:
            return config._access_token

        if not config.corp_id or not config.corp_secret:
            logger.error("WeChat Work corp_id or corp_secret not configured")
            return None

        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={config.corp_id}&corpsecret={config.corp_secret}"
        )

        try:
            response = await self.http.get(url)
            data = response.json()

            if data.get("errcode") == 0:
                config._access_token = data["access_token"]
                config._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
                return config._access_token
            else:
                logger.error(f"Failed to get access token: {data.get('errmsg')}")
                return None
        except Exception as e:
            logger.error(f"Access token request failed: {e}")
            return None

    @staticmethod
    def _format_markdown(message: NotificationMessage) -> str:
        """Format a notification as WeChat markdown."""
        priority_emoji = {
            NotificationPriority.LOW: "",
            NotificationPriority.NORMAL: "",
            NotificationPriority.HIGH: "**[Important]** ",
            NotificationPriority.URGENT: "**[URGENT]** ",
        }
        prefix = priority_emoji.get(message.priority, "")
        return f"{prefix}**{message.title}**\n\n{message.body}"

    @staticmethod
    def _generate_sign(timestamp: str, key: str) -> str:
        """Generate HMAC-SHA256 signature for webhook authentication."""
        string_to_sign = f"{timestamp}\n{key}"
        hmac_code = hmac.new(
            key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        import base64
        return base64.b64encode(hmac_code).decode("utf-8")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None
