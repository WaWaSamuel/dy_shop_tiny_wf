"""Response generator for customer feedback.

Produces appropriate replies based on feedback classification:
positive reviews get thank-you messages, negative reviews get apologies
(pending human approval), and FAQ matches produce knowledge-base answers.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.modules.feedback.schemas import (
    FeedbackEvent,
    FeedbackType,
    KBEntry,
    Sentiment,
)

logger = logging.getLogger(__name__)

# Template-based responses for common scenarios
_THANK_TEMPLATES = [
    "亲，感谢您的好评！您的满意是我们最大的动力~ 期待您的再次光临！",
    "感谢亲的认可！我们会继续努力为您提供优质商品和服务~ 祝您生活愉快！",
    "谢谢亲的五星好评！如有任何需要随时联系我们哦~ 希望您购物愉快！",
]

_APOLOGY_TEMPLATES = [
    "亲，非常抱歉给您带来不好的体验。我们已经记录了您的反馈，会尽快为您处理。请问方便描述一下具体情况吗？我们会第一时间为您解决。",
    "很抱歉让您失望了，亲。我们非常重视您的意见，已安排专人跟进处理。请您稍等，我们会尽快联系您协商解决方案。",
]


class ResponseGenerator:
    """Generates reply content for customer feedback events.

    Supports template-based quick replies, KB-matched answers,
    and LLM-generated responses for complex scenarios.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        self._thank_index = 0
        self._apology_index = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    def generate_thank_reply(self, event: FeedbackEvent) -> str:
        """Generate a thank-you reply for positive reviews (4-5 stars).

        Rotates through template responses to avoid repetition.

        Args:
            event: The positive feedback event.

        Returns:
            Generated thank-you reply text.
        """
        template = _THANK_TEMPLATES[self._thank_index % len(_THANK_TEMPLATES)]
        self._thank_index += 1

        # Personalize if customer name is available
        if event.customer_name:
            template = template.replace("亲", f"{event.customer_name}亲")

        return template

    def generate_apology_reply(self, event: FeedbackEvent) -> str:
        """Generate an apology reply for negative reviews (1-2 stars).

        These replies are flagged for human approval before sending.

        Args:
            event: The negative feedback event.

        Returns:
            Generated apology reply text (draft for human review).
        """
        template = _APOLOGY_TEMPLATES[self._apology_index % len(_APOLOGY_TEMPLATES)]
        self._apology_index += 1

        # Personalize
        if event.customer_name:
            template = template.replace("亲", f"{event.customer_name}亲")

        # Add context-specific note based on feedback type
        if event.feedback_type == FeedbackType.LOGISTICS:
            template += "\n\n关于物流问题，我们会与快递公司沟通确认配送情况。"
        elif event.feedback_type == FeedbackType.PRODUCT_QUALITY:
            template += "\n\n关于商品质量问题，我们支持7天无理由退换货，也可以为您安排补发。"
        elif event.feedback_type == FeedbackType.PRICING:
            template += "\n\n关于价格问题，我们会核实并为您提供合理的解决方案。"

        return template

    def generate_faq_reply(self, question: str, kb_match: KBEntry) -> str:
        """Generate a reply based on a knowledge base match.

        Wraps the KB answer with appropriate greeting/closing.

        Args:
            question: The customer's original question.
            kb_match: The matched knowledge base entry.

        Returns:
            Formatted reply incorporating the KB answer.
        """
        reply = f"亲，关于您咨询的问题：\n\n{kb_match.answer}"

        # Add helpful closing
        reply += "\n\n如果还有其他问题，随时联系我们哦~"
        return reply

    async def generate_llm_reply(self, event: FeedbackEvent) -> str:
        """Generate an LLM-drafted response for complex queries.

        Used when no FAQ match exists and the situation requires
        a contextual, nuanced response.

        Args:
            event: The feedback event requiring a response.

        Returns:
            LLM-generated reply text (draft for human review if urgent).
        """
        prompt = f"""You are a professional customer service representative for a Douyin
(抖音) e-commerce shop. Generate a helpful, empathetic reply to the following
customer feedback. Keep the response concise (under 150 characters), polite,
and solution-oriented. Write in Chinese.

Customer feedback source: {event.source.value}
Star rating: {event.star_rating or 'N/A'}
Feedback type: {event.feedback_type.value if event.feedback_type else 'unknown'}
Sentiment: {event.sentiment.value if event.sentiment else 'unknown'}

Customer message:
\"\"\"
{event.content[:500]}
\"\"\"

Requirements:
1. Address the customer's specific concern
2. Offer a concrete next step or solution
3. Be warm and professional
4. Use natural Chinese (not overly formal)

Reply:"""

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
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()

            # Remove any quotes the LLM might wrap the reply in
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1]

            logger.info(
                "Generated LLM reply for event=%s, length=%d",
                event.id,
                len(reply),
            )
            return reply

        except httpx.HTTPError as e:
            logger.error("LLM reply generation failed: %s", e)
            # Fallback to generic response
            return (
                "亲，感谢您的反馈！我们已收到您的消息，"
                "客服小伙伴会尽快为您处理，请耐心等待~"
            )
        finally:
            if self._http_client is None:
                await client.aclose()

    async def generate_response(self, event: FeedbackEvent, kb_match: KBEntry | None = None) -> str:
        """Main entry point: generate the appropriate response based on classification.

        Decision logic:
        - Positive reviews (4-5 stars): template thank-you
        - FAQ match with high confidence: KB-based reply
        - Negative/angry sentiment: apology (requires approval)
        - Otherwise: LLM-generated reply

        Args:
            event: The classified feedback event.
            kb_match: Optional knowledge base match if found.

        Returns:
            The generated reply text.
        """
        # Positive reviews: auto-reply with thanks
        if event.star_rating and event.star_rating >= 4 and event.sentiment == Sentiment.POSITIVE:
            return self.generate_thank_reply(event)

        # FAQ match with good confidence
        if kb_match and kb_match.similarity_score >= 0.8:
            return self.generate_faq_reply(event.content, kb_match)

        # Negative/angry: apology template (will need human approval)
        if event.sentiment in (Sentiment.NEGATIVE, Sentiment.ANGRY):
            return self.generate_apology_reply(event)

        # Complex case: use LLM
        return await self.generate_llm_reply(event)
