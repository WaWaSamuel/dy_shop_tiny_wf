"""Content generator for design assets.

Uses AI to generate marketing copy, scene descriptions, and structured content
for product detail page sections.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AI_TEXT_API_BASE_URL = os.getenv("AI_TEXT_API_BASE_URL", "http://ai-text-service:8000")
AI_TEXT_API_KEY = os.getenv("AI_TEXT_API_KEY", "")


class DesignContentGenerator:
    """Generates text and content for design assets using AI."""

    def __init__(
        self,
        api_base_url: str = AI_TEXT_API_BASE_URL,
        api_key: str = AI_TEXT_API_KEY,
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate_feature_copy(self, product_info: dict) -> list[str]:
        """Generate 3-5 selling points / feature copy lines for a product.

        Args:
            product_info: Dictionary with product details including:
                - name: Product name
                - category: Product category
                - description: Product description
                - attributes: dict of product attributes

        Returns:
            List of 3-5 concise selling point strings.
        """
        logger.info("Generating feature copy for: %s", product_info.get("name", "unknown"))

        prompt = self._build_feature_prompt(product_info)

        try:
            client = await self._get_client()
            response = await client.post(
                "/v1/generate-text",
                json={
                    "prompt": prompt,
                    "max_tokens": 500,
                    "temperature": 0.7,
                    "format": "list",
                },
            )
            response.raise_for_status()
            data = response.json()

            features = data.get("results", [])
            if not features:
                features = self._fallback_feature_copy(product_info)

            # Ensure 3-5 items
            features = features[:5]
            if len(features) < 3:
                features.extend(self._fallback_feature_copy(product_info)[: 3 - len(features)])

            logger.info("Generated %d feature copy lines", len(features))
            return features

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("AI text generation failed, using fallback: %s", str(e))
            return self._fallback_feature_copy(product_info)

    def _build_feature_prompt(self, product_info: dict) -> str:
        """Build a prompt for generating feature selling points."""
        name = product_info.get("name", "Product")
        category = product_info.get("category", "")
        description = product_info.get("description", "")
        attributes = product_info.get("attributes", {})

        attrs_text = ", ".join(f"{k}: {v}" for k, v in attributes.items()) if attributes else ""

        return (
            f"Generate 3-5 concise, compelling selling points for an e-commerce product listing.\n"
            f"Product: {name}\n"
            f"Category: {category}\n"
            f"Description: {description}\n"
            f"Attributes: {attrs_text}\n\n"
            f"Requirements:\n"
            f"- Each point should be 4-8 Chinese characters or 3-6 English words\n"
            f"- Focus on key benefits and differentiators\n"
            f"- Suitable for overlay text on product images\n"
            f"- Use action words and emotional appeal"
        )

    def _fallback_feature_copy(self, product_info: dict) -> list[str]:
        """Generate basic feature copy without AI when the API is unavailable."""
        name = product_info.get("name", "Product")
        category = product_info.get("category", "General")

        fallback_templates = {
            "clothing": ["Premium Fabric", "Comfortable Fit", "Trendy Design"],
            "electronics": ["High Performance", "Durable Build", "Smart Features"],
            "food": ["Fresh Ingredients", "Authentic Taste", "Premium Quality"],
            "beauty": ["Gentle Formula", "Visible Results", "Premium Ingredients"],
            "default": ["Premium Quality", "Great Value", "Customer Favorite"],
        }

        base = fallback_templates.get(category, fallback_templates["default"])
        return [f"{name} - {point}" if len(point) < 15 else point for point in base]

    async def generate_scene_description(self, product_name: str, category: str) -> str:
        """Generate a scene description prompt for AI image generation.

        Args:
            product_name: Name of the product.
            category: Product category.

        Returns:
            A detailed scene description suitable for AI image generation.
        """
        logger.info("Generating scene description for: %s (%s)", product_name, category)

        prompt = (
            f"Generate a detailed scene description for product photography.\n"
            f"Product: {product_name}\n"
            f"Category: {category}\n\n"
            f"Requirements:\n"
            f"- Describe a realistic usage scenario\n"
            f"- Include lighting, environment, mood details\n"
            f"- Suitable as an AI image generation prompt\n"
            f"- Professional e-commerce photography style\n"
            f"- 2-3 sentences maximum"
        )

        try:
            client = await self._get_client()
            response = await client.post(
                "/v1/generate-text",
                json={
                    "prompt": prompt,
                    "max_tokens": 200,
                    "temperature": 0.8,
                },
            )
            response.raise_for_status()
            data = response.json()
            scene = data.get("result", "")
            if scene:
                return scene
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("AI scene description failed, using fallback: %s", str(e))

        return self._fallback_scene_description(product_name, category)

    def _fallback_scene_description(self, product_name: str, category: str) -> str:
        """Generate a basic scene description without AI."""
        scenes = {
            "clothing": (
                f"A well-lit fashion photography setting with {product_name} displayed on a "
                f"minimalist background, soft directional lighting creating gentle shadows, "
                f"modern urban lifestyle atmosphere."
            ),
            "electronics": (
                f"A clean modern desk setup with {product_name} as the focal point, "
                f"soft ambient lighting, minimal clutter, tech-forward professional environment."
            ),
            "food": (
                f"A rustic kitchen scene with {product_name} beautifully plated, "
                f"warm natural lighting from a window, fresh ingredients as props, "
                f"appetizing food photography style."
            ),
            "beauty": (
                f"An elegant vanity setup with {product_name} positioned among soft fabrics, "
                f"gentle rose-gold lighting, fresh flowers as accent, luxury beauty editorial style."
            ),
        }
        return scenes.get(
            category,
            f"Professional product photography of {product_name} in a clean, well-lit "
            f"modern setting with complementary props, soft natural lighting, "
            f"premium e-commerce style.",
        )

    async def generate_detail_sections(self, product_info: dict, category: str) -> dict:
        """Generate content for each section of a product detail page.

        Args:
            product_info: Dictionary with full product information.
            category: Product category.

        Returns:
            Dictionary mapping section names to their generated content:
                - hero: dict with title, subtitle
                - features: list of feature dicts (icon, title, description)
                - specifications: list of spec dicts (label, value)
                - usage_scenarios: list of scenario descriptions
                - size_chart: dict with headers and rows (if applicable)
                - brand_story: dict with title, text
                - cta: dict with headline, subtext, button_text
        """
        logger.info("Generating detail sections for: %s", product_info.get("name", "unknown"))

        name = product_info.get("name", "Product")
        description = product_info.get("description", "")
        attributes = product_info.get("attributes", {})

        prompt = (
            f"Generate structured content for a product detail page on Douyin Shop.\n"
            f"Product: {name}\n"
            f"Category: {category}\n"
            f"Description: {description}\n"
            f"Attributes: {attributes}\n\n"
            f"Generate content for these sections: hero, features, specifications, "
            f"usage_scenarios, brand_story, cta.\n"
            f"Return as structured JSON."
        )

        try:
            client = await self._get_client()
            response = await client.post(
                "/v1/generate-text",
                json={
                    "prompt": prompt,
                    "max_tokens": 1500,
                    "temperature": 0.6,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            sections = data.get("result", {})
            if sections and isinstance(sections, dict):
                return self._validate_sections(sections, product_info, category)
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("AI detail section generation failed, using fallback: %s", str(e))

        return self._fallback_detail_sections(product_info, category)

    def _validate_sections(self, sections: dict, product_info: dict, category: str) -> dict:
        """Validate and fill in missing sections with fallback content."""
        fallback = self._fallback_detail_sections(product_info, category)
        for key in fallback:
            if key not in sections or not sections[key]:
                sections[key] = fallback[key]
        return sections

    def _fallback_detail_sections(self, product_info: dict, category: str) -> dict:
        """Generate fallback detail page section content."""
        name = product_info.get("name", "Product")
        description = product_info.get("description", "A premium quality product.")
        attributes = product_info.get("attributes", {})

        return {
            "hero": {
                "title": name,
                "subtitle": description[:80] if len(description) > 80 else description,
            },
            "features": [
                {"icon": "star", "title": "Premium Quality", "description": "Crafted with the finest materials"},
                {"icon": "shield", "title": "Durable Design", "description": "Built to last through daily use"},
                {"icon": "heart", "title": "Customer Favorite", "description": "Loved by thousands of buyers"},
            ],
            "specifications": [
                {"label": k, "value": str(v)} for k, v in list(attributes.items())[:8]
            ] or [
                {"label": "Material", "value": "Premium"},
                {"label": "Origin", "value": "Domestic"},
            ],
            "usage_scenarios": [
                f"Perfect for daily use - {name} fits seamlessly into your routine.",
                f"Ideal as a gift - Premium packaging and quality make {name} a thoughtful present.",
                f"Great for any occasion - versatile design suits various settings.",
            ],
            "size_chart": {
                "headers": ["Size", "Dimensions", "Weight"],
                "rows": [["Standard", "See product page", "See product page"]],
            },
            "brand_story": {
                "title": "Our Promise",
                "text": (
                    f"We are committed to delivering exceptional quality with {name}. "
                    f"Every detail is carefully considered to ensure your satisfaction."
                ),
            },
            "cta": {
                "headline": "Order Now",
                "subtext": "Limited stock available - don't miss out!",
                "button_text": "Add to Cart",
            },
        }
