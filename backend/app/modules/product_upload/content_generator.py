"""AI-powered content generation for product listings.

Generates 抖店-optimized titles, descriptions, SEO keywords, and performs
prohibited word checks to maximize listing approval rates.
"""

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Common prohibited words in e-commerce listings (违禁词)
# This is a subset; the full list should be maintained in a database or config file.
PROHIBITED_WORDS: list[str] = [
    "最好", "第一", "顶级", "极品", "国家级", "全网最低",
    "绝对", "万能", "特效", "祖传", "抢购", "秒杀",
    "仅此一次", "错过再无", "史无前例", "全民疯抢",
    "国家免检", "驰名商标", "质量免检", "无需申请",
    "保证治愈", "根治", "药到病除", "一次见效",
    "假一赔万", "假一赔十", "全国首家",
]


@dataclass
class ContentConfig:
    """Configuration for content generation."""

    max_title_length: int = 30
    max_description_length: int = 2000
    max_keywords: int = 10
    model: str = "gpt-4o-mini"
    temperature: float = 0.7


class AIContentGenerator:
    """Generates optimized product content using LLM services.

    Produces titles, descriptions, and keywords tailored for
    抖店 listing requirements and search optimization.
    """

    def __init__(self, config: ContentConfig | None = None) -> None:
        self.config = config or ContentConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for AI API calls."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.AI_API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate_title(
        self,
        product_name: str,
        category: str,
        keywords: list[str] | None = None,
    ) -> str:
        """Generate a 抖店-optimized product title.

        Format: brand + category + selling point + keyword
        Maximum length: 30 characters.

        Args:
            product_name: Original product name or description.
            category: Product category for context.
            keywords: Optional SEO keywords to incorporate.

        Returns:
            Optimized title string (max 30 chars).
        """
        keywords_str = "、".join(keywords) if keywords else "无"

        prompt = (
            "你是一个抖店商品标题优化专家。请根据以下信息生成一个优化的商品标题。\n\n"
            "要求：\n"
            f"1. 总长度不超过{self.config.max_title_length}个字符\n"
            "2. 格式：品牌+品类+卖点+关键词\n"
            "3. 不要使用违禁词（如：最好、第一、顶级等）\n"
            "4. 要吸引点击，突出核心卖点\n"
            "5. 直接返回标题文本，不要额外解释\n\n"
            f"商品名称：{product_name}\n"
            f"类目：{category}\n"
            f"关键词参考：{keywords_str}\n\n"
            "优化后的标题："
        )

        title = await self._call_llm(prompt)
        # Ensure title respects max length
        title = title.strip().strip('"').strip("'")
        if len(title) > self.config.max_title_length:
            title = title[: self.config.max_title_length]

        logger.info(
            "Generated title for '%s': '%s' (%d chars)",
            product_name,
            title,
            len(title),
        )
        return title

    async def generate_description(self, product_info: dict) -> str:
        """Generate a structured product description.

        Sections: highlights, specifications, usage scenarios, packaging.

        Args:
            product_info: Dictionary with product details (name, features,
                specs, materials, etc.).

        Returns:
            Structured description string.
        """
        info_text = "\n".join(f"- {k}: {v}" for k, v in product_info.items())

        prompt = (
            "你是一个专业的抖店商品描述撰写专家。请根据以下商品信息生成结构化的商品描述。\n\n"
            "要求：\n"
            f"1. 总长度不超过{self.config.max_description_length}字\n"
            "2. 包含以下四个部分，每部分用【】标注：\n"
            "   【产品亮点】- 3-5个核心卖点\n"
            "   【规格参数】- 关键参数列表\n"
            "   【适用场景】- 2-3个使用场景描述\n"
            "   【包装说明】- 包装内容物和售后说明\n"
            "3. 不要使用违禁词\n"
            "4. 语言简洁有力，突出差异化\n\n"
            f"商品信息：\n{info_text}\n\n"
            "商品描述："
        )

        description = await self._call_llm(prompt)
        description = description.strip()

        if len(description) > self.config.max_description_length:
            description = description[: self.config.max_description_length]

        logger.info(
            "Generated description for '%s' (%d chars)",
            product_info.get("name", "unknown"),
            len(description),
        )
        return description

    async def extract_seo_keywords(
        self,
        category: str,
        product_name: str,
    ) -> list[str]:
        """Extract SEO keywords from trending search terms.

        Args:
            category: Product category.
            product_name: Product name for keyword extraction.

        Returns:
            List of relevant SEO keywords (max 10).
        """
        prompt = (
            "你是一个抖店SEO关键词专家。请根据以下商品信息提取最相关的搜索关键词。\n\n"
            "要求：\n"
            f"1. 返回{self.config.max_keywords}个以内的关键词\n"
            "2. 每个关键词一行\n"
            "3. 优先选择搜索量大、竞争度适中的关键词\n"
            "4. 包含长尾关键词和核心关键词的组合\n"
            "5. 只返回关键词列表，不要编号或额外说明\n\n"
            f"商品类目：{category}\n"
            f"商品名称：{product_name}\n\n"
            "关键词列表："
        )

        result = await self._call_llm(prompt)
        keywords = [
            kw.strip().strip("-").strip("•").strip()
            for kw in result.strip().split("\n")
            if kw.strip()
        ]
        # Limit to max_keywords
        keywords = keywords[: self.config.max_keywords]

        logger.info(
            "Extracted %d keywords for '%s' in category '%s'",
            len(keywords),
            product_name,
            category,
        )
        return keywords

    def check_prohibited_words(self, text: str) -> list[str]:
        """Scan text for prohibited words (违禁词).

        Checks against the known list of words that will cause
        listing rejection on 抖店.

        Args:
            text: Text content to scan (title, description, etc.).

        Returns:
            List of prohibited words found in the text.
        """
        found: list[str] = []
        text_lower = text.lower()

        for word in PROHIBITED_WORDS:
            if word in text_lower:
                found.append(word)

        if found:
            logger.warning(
                "Found %d prohibited words in text: %s",
                len(found),
                ", ".join(found),
            )

        return found

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM API with a prompt and return the response text.

        Args:
            prompt: The prompt to send to the model.

        Returns:
            Generated text response.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        client = await self._get_client()

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的电商内容优化助手，专注于抖音电商（抖店）平台。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": 1024,
        }

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "LLM API request failed: status=%d, body=%s",
                e.response.status_code,
                e.response.text[:500],
            )
            raise
        except (KeyError, IndexError) as e:
            logger.error("Unexpected LLM response structure: %s", e)
            raise ValueError("Invalid response from AI service") from e
