"""Core feedback service orchestrating ingestion, classification, and response.

Handles polling 抖店 APIs for reviews and after-sale tickets, maintaining a
WebSocket connection to 飞鸽 IM for real-time messages, and coordinating the
classification and response pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter
from app.core.security import sign_request
from app.modules.feedback.classifier import AIClassifier
from app.modules.feedback.knowledge_base import KnowledgeBaseManager
from app.modules.feedback.responder import ResponseGenerator
from app.modules.feedback.schemas import (
    FeedbackEvent,
    FeedbackSource,
    FeedbackStatus,
    FeedbackType,
    Sentiment,
)

logger = logging.getLogger(__name__)

_DOUYIN_API_BASE = "https://openapi-fxg.jinritemai.com"


class FeedbackService:
    """Orchestrates the full customer feedback lifecycle.

    Responsibilities:
    - Ingest feedback from multiple channels (reviews, IM, after-sale)
    - Classify feedback using AI
    - Generate appropriate responses
    - Submit replies through the correct channel API
    """

    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._http_client = http_client
        self._classifier = AIClassifier(rate_limiter=rate_limiter, http_client=http_client)
        self._responder = ResponseGenerator(http_client=http_client)
        self._knowledge_base = KnowledgeBaseManager(http_client=http_client)

        # In-memory event store; production would use database
        self._events: dict[str, FeedbackEvent] = {}
        self._ws_connection: Any = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    async def _api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a signed request to the 抖店 API.

        Args:
            method: HTTP method.
            path: API path (e.g., "/product/reviewList").
            params: Query parameters.
            body: JSON body for POST requests.

        Returns:
            Parsed response data dict.

        Raises:
            DouyinAPIError: On API failures.
        """
        from app.core.exceptions import DouyinAPIError

        if self._rate_limiter:
            await self._rate_limiter.acquire("douyin_default")

        params = params or {}
        body_str = json.dumps(body, ensure_ascii=False) if body else ""

        # Generate signed headers
        sign_headers = sign_request(
            method=method,
            path=path,
            params=params,
            body=body_str,
        )

        headers = {
            "Content-Type": "application/json",
            "access-token": settings.DOUYIN_ACCESS_TOKEN,
            **sign_headers,
        }

        url = f"{_DOUYIN_API_BASE}{path}"
        client = await self._get_client()

        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params, headers=headers)
            else:
                response = await client.post(
                    url, params=params, headers=headers, content=body_str
                )

            if response.status_code != 200:
                raise DouyinAPIError(
                    message=f"API request to {path} failed",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            data = response.json()
            if data.get("err_no") != 0:
                raise DouyinAPIError(
                    message=f"API error: {data.get('message', 'unknown')}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return data.get("data", {})

        finally:
            if self._http_client is None:
                await client.aclose()

    async def ingest_reviews(self) -> list[FeedbackEvent]:
        """Poll 抖店 API /product/reviewList for new product reviews.

        Called every 5 minutes by the periodic task. Normalizes each review
        into a FeedbackEvent for the classification pipeline.

        Returns:
            List of newly ingested FeedbackEvent objects.
        """
        logger.info("Polling for new product reviews")
        now = datetime.utcnow()
        five_minutes_ago = now - timedelta(minutes=5)

        try:
            data = await self._api_request(
                method="POST",
                path="/product/reviewList",
                body={
                    "start_time": int(five_minutes_ago.timestamp()),
                    "end_time": int(now.timestamp()),
                    "page": 1,
                    "size": 100,
                    "comment_type": 0,  # All types
                },
            )
        except Exception as e:
            logger.error("Failed to fetch reviews: %s", e)
            return []

        reviews = data.get("data", [])
        events: list[FeedbackEvent] = []

        for review in reviews:
            event_id = str(uuid.uuid4())
            event = FeedbackEvent(
                id=event_id,
                source=FeedbackSource.REVIEW,
                external_id=str(review.get("comment_id", "")),
                order_id=str(review.get("order_id", "")),
                product_id=str(review.get("product_id", "")),
                customer_id=str(review.get("user_id", "")),
                customer_name=review.get("user_name", ""),
                content=review.get("content", ""),
                star_rating=review.get("star", 5),
                images=review.get("image_list", []),
                created_at=datetime.fromtimestamp(review.get("create_time", 0)),
                received_at=now,
            )
            self._events[event_id] = event
            events.append(event)

        logger.info("Ingested %d new reviews", len(events))
        return events

    async def ingest_im_messages(self) -> None:
        """Connect to 飞鸽 IM API via WebSocket for real-time messages.

        Maintains a persistent WebSocket connection and processes incoming
        customer messages as they arrive. Runs as a long-lived coroutine.
        """
        import websockets

        ws_url = (
            f"wss://openapi-fxg.jinritemai.com/im/ws"
            f"?app_key={settings.DOUYIN_APP_KEY}"
            f"&access_token={settings.DOUYIN_ACCESS_TOKEN}"
        )

        logger.info("Connecting to 飞鸽 IM WebSocket")

        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    self._ws_connection = ws
                    logger.info("飞鸽 IM WebSocket connected")

                    async for raw_message in ws:
                        try:
                            message_data = json.loads(raw_message)
                            await self._handle_im_message(message_data)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from IM WebSocket")
                        except Exception as e:
                            logger.error("Error processing IM message: %s", e)

            except Exception as e:
                logger.error("IM WebSocket disconnected: %s. Reconnecting in 5s...", e)
                self._ws_connection = None
                await asyncio.sleep(5)

    async def _handle_im_message(self, message_data: dict[str, Any]) -> None:
        """Process a single IM message from the WebSocket feed."""
        msg_type = message_data.get("msg_type", "")
        if msg_type != "customer_message":
            return  # Ignore system messages, read receipts, etc.

        event_id = str(uuid.uuid4())
        event = FeedbackEvent(
            id=event_id,
            source=FeedbackSource.IM,
            external_id=str(message_data.get("msg_id", "")),
            order_id=str(message_data.get("order_id", "")),
            product_id=str(message_data.get("product_id", "")),
            customer_id=str(message_data.get("user_id", "")),
            customer_name=message_data.get("user_name", ""),
            content=message_data.get("content", ""),
            received_at=datetime.utcnow(),
        )
        self._events[event_id] = event

        # Immediately process IM messages for fast response
        await self.classify_feedback(event)
        await self.generate_response(event)

        logger.info("Processed IM message event_id=%s", event_id)

    async def ingest_after_sale_tickets(self) -> list[FeedbackEvent]:
        """Poll 抖店 API /order/serviceDetail for after-sale disputes.

        Called every 3 minutes by the periodic task. These are higher-urgency
        events that may involve refunds or returns.

        Returns:
            List of newly ingested after-sale FeedbackEvent objects.
        """
        logger.info("Polling for after-sale tickets")
        now = datetime.utcnow()
        three_minutes_ago = now - timedelta(minutes=3)

        try:
            data = await self._api_request(
                method="POST",
                path="/order/serviceDetail",
                body={
                    "start_time": int(three_minutes_ago.timestamp()),
                    "end_time": int(now.timestamp()),
                    "page": 1,
                    "size": 50,
                    "status": 1,  # Active/open tickets
                },
            )
        except Exception as e:
            logger.error("Failed to fetch after-sale tickets: %s", e)
            return []

        tickets = data.get("data", [])
        events: list[FeedbackEvent] = []

        for ticket in tickets:
            event_id = str(uuid.uuid4())
            event = FeedbackEvent(
                id=event_id,
                source=FeedbackSource.AFTER_SALE,
                external_id=str(ticket.get("aftersale_id", "")),
                order_id=str(ticket.get("order_id", "")),
                product_id=str(ticket.get("product_id", "")),
                customer_id=str(ticket.get("user_id", "")),
                customer_name=ticket.get("user_name", ""),
                content=ticket.get("reason", "") + " " + ticket.get("description", ""),
                refund_amount=float(ticket.get("refund_amount", 0)) / 100,  # Convert cents
                images=ticket.get("evidence_images", []),
                created_at=datetime.fromtimestamp(ticket.get("create_time", 0)),
                received_at=now,
            )
            self._events[event_id] = event
            events.append(event)

        logger.info("Ingested %d after-sale tickets", len(events))
        return events

    async def classify_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        """Run AI classification pipeline on a feedback event.

        Determines feedback type, sentiment, and urgency score.
        Updates the event in-place and in the event store.

        Args:
            event: The feedback event to classify.

        Returns:
            The updated event with classification results.
        """
        event.status = FeedbackStatus.CLASSIFYING

        try:
            event.feedback_type = await self._classifier.classify_type(event.content)
            event.sentiment = await self._classifier.analyze_sentiment(event.content)
            event.urgency_score = await self._classifier.score_urgency(event)
        except Exception as e:
            logger.error("Classification failed for event %s: %s", event.id, e)
            event.feedback_type = FeedbackType.OTHER
            event.sentiment = Sentiment.NEUTRAL
            event.urgency_score = 3  # Default to medium urgency on failure

        # Update store
        self._events[event.id] = event
        logger.info(
            "Classified event=%s type=%s sentiment=%s urgency=%d",
            event.id,
            event.feedback_type,
            event.sentiment,
            event.urgency_score,
        )
        return event

    async def generate_response(self, event: FeedbackEvent) -> FeedbackEvent:
        """Generate an appropriate response for a classified feedback event.

        Uses knowledge base search first, then falls back to template or
        LLM-generated responses based on classification.

        Args:
            event: The classified feedback event.

        Returns:
            The updated event with generated reply.
        """
        # Search knowledge base for relevant FAQ
        kb_match = None
        if event.content:
            kb_results = await self._knowledge_base.search(
                query=event.content,
                product_id=event.product_id or None,
            )
            if kb_results:
                kb_match = kb_results[0]

        # Generate response
        reply = await self._responder.generate_response(event, kb_match)
        event.auto_reply = reply

        # Determine if auto-send or needs approval
        needs_approval = (
            event.sentiment in (Sentiment.NEGATIVE, Sentiment.ANGRY)
            or event.urgency_score >= 4
            or event.refund_amount > 100
        )

        if needs_approval:
            event.status = FeedbackStatus.AWAITING_APPROVAL
        else:
            event.status = FeedbackStatus.DRAFT_READY

        self._events[event.id] = event
        return event

    async def check_knowledge_base(self, question: str, product_id: str | None = None) -> list:
        """Search the knowledge base for FAQ matches.

        Args:
            question: The customer's question text.
            product_id: Optional product ID to narrow results.

        Returns:
            List of matching KBEntry objects.
        """
        return await self._knowledge_base.search(
            query=question,
            product_id=product_id,
        )

    async def submit_reply(
        self,
        event_id: str,
        reply_content: str,
        channel: FeedbackSource | None = None,
    ) -> bool:
        """Send the reply through the appropriate channel API.

        Dispatches to the correct API based on the feedback source
        (review reply, IM message, or after-sale response).

        Args:
            event_id: The feedback event ID.
            reply_content: The reply text to send.
            channel: Override channel; defaults to event's source.

        Returns:
            True if reply was sent successfully.

        Raises:
            ValueError: If event_id is not found.
        """
        event = self._events.get(event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")

        source = channel or event.source
        success = False

        try:
            if source == FeedbackSource.REVIEW:
                success = await self._reply_to_review(event, reply_content)
            elif source == FeedbackSource.IM:
                success = await self._reply_via_im(event, reply_content)
            elif source == FeedbackSource.AFTER_SALE:
                success = await self._reply_to_after_sale(event, reply_content)

            if success:
                event.final_reply = reply_content
                event.replied_at = datetime.utcnow()
                event.status = FeedbackStatus.REPLIED
                self._events[event_id] = event
                logger.info("Reply sent for event=%s via %s", event_id, source.value)

        except Exception as e:
            logger.error("Failed to submit reply for event=%s: %s", event_id, e)
            success = False

        return success

    async def _reply_to_review(self, event: FeedbackEvent, content: str) -> bool:
        """Submit a reply to a product review via 抖店 API."""
        await self._api_request(
            method="POST",
            path="/product/replyReview",
            body={
                "comment_id": event.external_id,
                "content": content,
            },
        )
        return True

    async def _reply_via_im(self, event: FeedbackEvent, content: str) -> bool:
        """Send an IM message reply via 飞鸽 API."""
        await self._api_request(
            method="POST",
            path="/im/sendMsg",
            body={
                "user_id": event.customer_id,
                "msg_type": "text",
                "content": json.dumps({"text": content}),
                "conversation_id": event.metadata.get("conversation_id", ""),
            },
        )
        return True

    async def _reply_to_after_sale(self, event: FeedbackEvent, content: str) -> bool:
        """Submit a response to an after-sale ticket."""
        await self._api_request(
            method="POST",
            path="/order/replyService",
            body={
                "aftersale_id": event.external_id,
                "content": content,
                "type": "text",
            },
        )
        return True

    # --- Query methods for the API router ---

    def get_event(self, event_id: str) -> FeedbackEvent | None:
        """Get a single feedback event by ID."""
        return self._events.get(event_id)

    def list_events(
        self,
        status: FeedbackStatus | None = None,
        feedback_type: FeedbackType | None = None,
        source: FeedbackSource | None = None,
        min_urgency: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[FeedbackEvent]:
        """List feedback events with optional filters.

        Args:
            status: Filter by processing status.
            feedback_type: Filter by classification type.
            source: Filter by feedback source channel.
            min_urgency: Minimum urgency score to include.
            offset: Pagination offset.
            limit: Maximum results to return.

        Returns:
            Filtered and paginated list of FeedbackEvent objects.
        """
        events = list(self._events.values())

        if status is not None:
            events = [e for e in events if e.status == status]
        if feedback_type is not None:
            events = [e for e in events if e.feedback_type == feedback_type]
        if source is not None:
            events = [e for e in events if e.source == source]
        if min_urgency is not None:
            events = [e for e in events if e.urgency_score >= min_urgency]

        # Sort by received_at descending (most recent first)
        events.sort(key=lambda e: e.received_at, reverse=True)
        return events[offset : offset + limit]

    def get_statistics(self) -> dict[str, Any]:
        """Compute feedback statistics.

        Returns:
            Dictionary with response time metrics, auto-reply rate,
            and sentiment breakdown.
        """
        events = list(self._events.values())
        total = len(events)

        if total == 0:
            return {
                "total_events": 0,
                "auto_reply_rate": 0.0,
                "avg_response_time_seconds": 0.0,
                "sentiment_breakdown": {},
                "type_breakdown": {},
                "status_breakdown": {},
            }

        # Response time calculation
        responded = [e for e in events if e.replied_at is not None]
        if responded:
            response_times = [
                (e.replied_at - e.received_at).total_seconds()
                for e in responded
            ]
            avg_response_time = sum(response_times) / len(response_times)
        else:
            avg_response_time = 0.0

        # Auto-reply rate (events that didn't require approval)
        auto_replied = [
            e for e in responded if e.status == FeedbackStatus.REPLIED and e.auto_reply == e.final_reply
        ]
        auto_reply_rate = len(auto_replied) / total if total > 0 else 0.0

        # Sentiment breakdown
        sentiment_counts: dict[str, int] = {}
        for e in events:
            key = e.sentiment.value if e.sentiment else "unclassified"
            sentiment_counts[key] = sentiment_counts.get(key, 0) + 1

        # Type breakdown
        type_counts: dict[str, int] = {}
        for e in events:
            key = e.feedback_type.value if e.feedback_type else "unclassified"
            type_counts[key] = type_counts.get(key, 0) + 1

        # Status breakdown
        status_counts: dict[str, int] = {}
        for e in events:
            status_counts[e.status.value] = status_counts.get(e.status.value, 0) + 1

        return {
            "total_events": total,
            "responded_count": len(responded),
            "auto_reply_rate": round(auto_reply_rate, 3),
            "avg_response_time_seconds": round(avg_response_time, 1),
            "sentiment_breakdown": sentiment_counts,
            "type_breakdown": type_counts,
            "status_breakdown": status_counts,
        }
