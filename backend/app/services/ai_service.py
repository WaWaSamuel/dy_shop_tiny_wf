"""Unified AI/LLM service interface.

Provides a single interface for LLM text generation, image generation,
background removal, and sentiment analysis with built-in rate limiting
and cost tracking.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, circuit_breakers
from app.core.config import settings
from app.core.exceptions import RateLimitExceeded

logger = logging.getLogger(__name__)

# Default models
DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_IMAGE_MODEL = "dall-e-3"

# Rate limiting: max requests per minute
AI_RATE_LIMIT_RPM = 60
AI_RATE_LIMIT_WINDOW = 60.0  # seconds


@dataclass
class CostTracker:
    """Tracks API usage costs across calls."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_image_generations: int = 0
    total_cost_usd: float = 0.0
    session_start: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    def record_chat(self, input_tokens: int, output_tokens: int, model: str) -> None:
        """Record a chat completion usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        # Approximate cost (model-dependent)
        if "gpt-4o" in model:
            self.total_cost_usd += (input_tokens * 2.5 + output_tokens * 10) / 1_000_000
        elif "gpt-4" in model:
            self.total_cost_usd += (input_tokens * 30 + output_tokens * 60) / 1_000_000
        else:
            self.total_cost_usd += (input_tokens * 0.15 + output_tokens * 0.6) / 1_000_000

    def record_image(self, size: str) -> None:
        """Record an image generation."""
        self.total_image_generations += 1
        # DALL-E 3 pricing approximation
        if size == "1024x1024":
            self.total_cost_usd += 0.04
        elif size == "1792x1024" or size == "1024x1792":
            self.total_cost_usd += 0.08
        else:
            self.total_cost_usd += 0.04

    def to_dict(self) -> dict:
        """Serialize cost tracking data."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_image_generations": self.total_image_generations,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "session_start": self.session_start,
        }


class AIService:
    """Unified AI/LLM service interface.

    Provides:
    - chat_completion: LLM text generation
    - generate_image: AI image generation
    - remove_background: Background removal API
    - analyze_sentiment: Sentiment analysis

    All methods include rate limiting and cost tracking.

    Usage:
        ai = AIService()
        response = await ai.chat_completion([{"role": "user", "content": "Hello"}])
        await ai.close()
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.AI_API_KEY
        self._base_url = (base_url or settings.AI_API_BASE_URL).rstrip("/")

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        # Circuit breaker
        self._circuit_breaker: CircuitBreaker = circuit_breakers.get(
            "ai_service",
            CircuitBreaker(name="ai_service", failure_threshold=3, cooldown_seconds=30.0),
        )

        # Rate limiting (simple in-memory sliding window)
        self._request_timestamps: list[float] = []

        # Cost tracking
        self.cost_tracker = CostTracker()

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a chat completion using the LLM.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: Model identifier (defaults to gpt-4o-mini).
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens in response.

        Returns:
            Generated text content.

        Raises:
            RateLimitExceeded: When AI rate limit is exhausted.
            Exception: On API errors after retry.
        """
        self._check_rate_limit()
        self._circuit_breaker.allow_request()

        model = model or DEFAULT_CHAT_MODEL

        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )

            if response.status_code != 200:
                self._circuit_breaker.record_failure()
                raise Exception(
                    f"AI chat completion failed: {response.status_code} - {response.text}"
                )

            result = response.json()
            self._circuit_breaker.record_success()

            # Track costs
            usage = result.get("usage", {})
            self.cost_tracker.record_chat(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=model,
            )

            # Extract content
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""

        except httpx.TimeoutException as exc:
            self._circuit_breaker.record_failure()
            logger.error("[AIService] Chat completion timeout: %s", exc)
            raise

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str = "vivid",
        model: str | None = None,
    ) -> str:
        """Generate an image using AI image generation API.

        Args:
            prompt: Text description of the desired image.
            size: Image dimensions (e.g., "1024x1024", "1792x1024").
            style: Image style ("vivid" or "natural").
            model: Image model identifier.

        Returns:
            URL of the generated image.

        Raises:
            Exception: On generation failure.
        """
        self._check_rate_limit()
        self._circuit_breaker.allow_request()

        model = model or DEFAULT_IMAGE_MODEL

        try:
            response = await self._client.post(
                "/images/generations",
                json={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "style": style,
                    "n": 1,
                    "response_format": "url",
                },
            )

            if response.status_code != 200:
                self._circuit_breaker.record_failure()
                raise Exception(
                    f"AI image generation failed: {response.status_code} - {response.text}"
                )

            result = response.json()
            self._circuit_breaker.record_success()

            # Track cost
            self.cost_tracker.record_image(size)

            # Extract URL
            data = result.get("data", [])
            if data:
                return data[0].get("url", "")
            return ""

        except httpx.TimeoutException as exc:
            self._circuit_breaker.record_failure()
            logger.error("[AIService] Image generation timeout: %s", exc)
            raise

    async def remove_background(self, image_url: str) -> str:
        """Remove background from an image.

        Uses an external background removal API (e.g., remove.bg compatible).

        Args:
            image_url: URL of the source image.

        Returns:
            URL of the processed image with background removed.

        Raises:
            Exception: On processing failure.
        """
        self._check_rate_limit()
        self._circuit_breaker.allow_request()

        try:
            # Use the AI service for background removal via specialized endpoint
            response = await self._client.post(
                "/images/edits",
                json={
                    "image": image_url,
                    "prompt": "Remove the background, keep only the main subject on transparent background",
                    "n": 1,
                    "response_format": "url",
                },
            )

            if response.status_code != 200:
                self._circuit_breaker.record_failure()
                raise Exception(
                    f"Background removal failed: {response.status_code} - {response.text}"
                )

            result = response.json()
            self._circuit_breaker.record_success()

            data = result.get("data", [])
            if data:
                return data[0].get("url", "")
            return ""

        except httpx.TimeoutException as exc:
            self._circuit_breaker.record_failure()
            logger.error("[AIService] Background removal timeout: %s", exc)
            raise

    async def analyze_sentiment(self, text: str) -> dict:
        """Analyze sentiment of a text string.

        Uses LLM-based sentiment classification.

        Args:
            text: Text to analyze.

        Returns:
            Dict with keys:
            - sentiment: "positive", "negative", or "neutral"
            - confidence: float 0-1
            - keywords: list of relevant keywords
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a sentiment analysis system. Analyze the following text "
                    "and respond in JSON format with keys: sentiment (positive/negative/neutral), "
                    "confidence (0-1 float), keywords (list of relevant terms)."
                ),
            },
            {"role": "user", "content": text},
        ]

        try:
            response_text = await self.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=256,
            )

            # Parse JSON response
            import json

            # Try to extract JSON from the response
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Strip markdown code blocks
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            result = json.loads(response_text)
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "confidence": float(result.get("confidence", 0.5)),
                "keywords": result.get("keywords", []),
            }

        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("[AIService] Sentiment analysis parse error: %s", exc)
            # Fallback: simple keyword-based analysis
            return self._fallback_sentiment(text)

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    # -------------------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------------------

    def _check_rate_limit(self) -> None:
        """Check and enforce in-memory rate limiting.

        Raises:
            RateLimitExceeded: If rate limit is exceeded.
        """
        now = time.time()
        window_start = now - AI_RATE_LIMIT_WINDOW

        # Remove timestamps outside the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > window_start
        ]

        if len(self._request_timestamps) >= AI_RATE_LIMIT_RPM:
            oldest_in_window = self._request_timestamps[0]
            retry_after = AI_RATE_LIMIT_WINDOW - (now - oldest_in_window)
            raise RateLimitExceeded(
                category="ai_service",
                retry_after=max(0.1, retry_after),
            )

        self._request_timestamps.append(now)

    # -------------------------------------------------------------------------
    # Fallback methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _fallback_sentiment(text: str) -> dict:
        """Simple keyword-based sentiment fallback when LLM is unavailable."""
        negative_keywords = [
            "差", "烂", "垃圾", "退货", "骗", "假", "坏", "不好", "失望",
            "bad", "terrible", "awful", "scam", "fake", "broken",
        ]
        positive_keywords = [
            "好", "棒", "赞", "满意", "喜欢", "推荐", "优秀", "完美",
            "good", "great", "excellent", "love", "recommend", "perfect",
        ]

        text_lower = text.lower()
        neg_count = sum(1 for kw in negative_keywords if kw in text_lower)
        pos_count = sum(1 for kw in positive_keywords if kw in text_lower)

        if neg_count > pos_count:
            sentiment = "negative"
            confidence = min(0.9, 0.5 + neg_count * 0.1)
        elif pos_count > neg_count:
            sentiment = "positive"
            confidence = min(0.9, 0.5 + pos_count * 0.1)
        else:
            sentiment = "neutral"
            confidence = 0.5

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "keywords": [],
        }
