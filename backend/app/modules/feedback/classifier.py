"""AI-powered feedback classifier.

Uses LLM to determine feedback type, sentiment, and urgency for
incoming customer feedback events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter
from app.modules.feedback.schemas import (
    ClassificationResult,
    FeedbackEvent,
    FeedbackType,
    Sentiment,
)

logger = logging.getLogger(__name__)

_TYPE_CLASSIFICATION_PROMPT = """You are a customer feedback classifier for a Douyin e-commerce shop.
Classify the following feedback into exactly ONE category:
- product_quality: complaints or praise about product quality, appearance, defects
- logistics: shipping speed, packaging damage, delivery issues
- pricing: price complaints, discount inquiries, price match requests
- customer_service: complaints about service attitude, response speed
- spam: irrelevant content, ads, test messages
- other: anything not fitting the above

Customer feedback:
\"\"\"
{content}
\"\"\"

Respond with ONLY a JSON object: {{"type": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}"""

_SENTIMENT_PROMPT = """Analyze the sentiment of this customer feedback for a Douyin e-commerce shop.
Classify sentiment as exactly one of: positive, neutral, negative, angry

Customer feedback:
\"\"\"
{content}
\"\"\"

Respond with ONLY a JSON object: {{"sentiment": "<sentiment>", "confidence": <0.0-1.0>}}"""


class AIClassifier:
    """LLM-based classifier for customer feedback events.

    Uses the configured AI API (OpenAI-compatible) for classification.
    Includes fallback heuristics when AI service is unavailable.
    """

    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._http_client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM API and return the response text."""
        if self._rate_limiter:
            await self._rate_limiter.acquire("ai_service")

        client = await self._get_client()
        try:
            response = await client.post(
                f"{settings.AI_API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 256,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        finally:
            if self._http_client is None:
                await client.aclose()

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            # Strip markdown code fences
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response: %s", text[:200])
            return {}

    async def classify_type(self, content: str) -> FeedbackType:
        """Classify feedback content into a FeedbackType category.

        Args:
            content: The raw feedback text from the customer.

        Returns:
            The determined FeedbackType enum value.
        """
        if not content.strip():
            return FeedbackType.OTHER

        try:
            prompt = _TYPE_CLASSIFICATION_PROMPT.format(content=content[:1000])
            response_text = await self._call_llm(prompt)
            result = self._parse_json_response(response_text)
            type_str = result.get("type", "other")
            return FeedbackType(type_str)
        except (ValueError, KeyError) as e:
            logger.warning("Classification parse error: %s", e)
            return self._fallback_classify_type(content)
        except httpx.HTTPError as e:
            logger.error("LLM API error during type classification: %s", e)
            return self._fallback_classify_type(content)

    async def analyze_sentiment(self, content: str) -> Sentiment:
        """Analyze the sentiment of customer feedback.

        Args:
            content: The raw feedback text.

        Returns:
            Sentiment enum value (positive/neutral/negative/angry).
        """
        if not content.strip():
            return Sentiment.NEUTRAL

        try:
            prompt = _SENTIMENT_PROMPT.format(content=content[:1000])
            response_text = await self._call_llm(prompt)
            result = self._parse_json_response(response_text)
            sentiment_str = result.get("sentiment", "neutral")
            return Sentiment(sentiment_str)
        except (ValueError, KeyError) as e:
            logger.warning("Sentiment parse error: %s", e)
            return self._fallback_analyze_sentiment(content)
        except httpx.HTTPError as e:
            logger.error("LLM API error during sentiment analysis: %s", e)
            return self._fallback_analyze_sentiment(content)

    async def score_urgency(self, event: FeedbackEvent) -> int:
        """Score the urgency of a feedback event from 1 (low) to 5 (critical).

        Scoring criteria:
        - Refund amount > 200 RMB: +1
        - Angry sentiment: +2, Negative: +1
        - Star rating 1: +2, rating 2: +1
        - After-sale source: +1
        - Content length > 200 chars (detailed complaint): +1

        The final score is clamped between 1 and 5.

        Args:
            event: The feedback event to score.

        Returns:
            Urgency score between 1 and 5.
        """
        score = 1

        # Refund amount factor
        if event.refund_amount > 500:
            score += 2
        elif event.refund_amount > 200:
            score += 1

        # Sentiment factor
        if event.sentiment == Sentiment.ANGRY:
            score += 2
        elif event.sentiment == Sentiment.NEGATIVE:
            score += 1

        # Star rating factor
        if event.star_rating is not None:
            if event.star_rating == 1:
                score += 2
            elif event.star_rating == 2:
                score += 1

        # Source factor - after-sale disputes are inherently more urgent
        from app.modules.feedback.schemas import FeedbackSource

        if event.source == FeedbackSource.AFTER_SALE:
            score += 1

        # Detail factor - longer complaints indicate serious issues
        if len(event.content) > 200:
            score += 1

        return min(max(score, 1), 5)

    def _fallback_classify_type(self, content: str) -> FeedbackType:
        """Heuristic fallback when LLM is unavailable."""
        content_lower = content.lower()
        keywords = {
            FeedbackType.LOGISTICS: [
                "物流", "快递", "配送", "发货", "包装", "运输", "签收", "派送",
            ],
            FeedbackType.PRODUCT_QUALITY: [
                "质量", "破损", "色差", "尺寸", "做工", "材质", "瑕疵", "坏了",
            ],
            FeedbackType.PRICING: [
                "价格", "贵", "便宜", "优惠", "折扣", "退差价", "涨价",
            ],
            FeedbackType.CUSTOMER_SERVICE: [
                "客服", "态度", "回复慢", "不理人", "服务",
            ],
        }
        for ftype, kws in keywords.items():
            if any(kw in content_lower for kw in kws):
                return ftype
        return FeedbackType.OTHER

    def _fallback_analyze_sentiment(self, content: str) -> Sentiment:
        """Heuristic fallback for sentiment analysis."""
        content_lower = content.lower()
        angry_words = ["垃圾", "骗子", "投诉", "举报", "差评", "太差", "恶心"]
        negative_words = ["不好", "失望", "一般", "退货", "退款", "不满意"]
        positive_words = ["好评", "满意", "不错", "推荐", "喜欢", "很好", "超赞"]

        if any(w in content_lower for w in angry_words):
            return Sentiment.ANGRY
        if any(w in content_lower for w in negative_words):
            return Sentiment.NEGATIVE
        if any(w in content_lower for w in positive_words):
            return Sentiment.POSITIVE
        return Sentiment.NEUTRAL
