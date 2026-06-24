"""Design templates for main images, detail pages, and promotional banners.

Provides template definitions including layout, style configurations, and section
structures used by the design asset generation pipeline.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TemplateStyle(str, Enum):
    """Available template styles."""
    CLEAN_GRADIENT = "clean_gradient"
    LIFESTYLE = "lifestyle"
    BOLD_TEXT = "bold_text"
    FESTIVAL_THEME = "festival_theme"


class DetailSection(str, Enum):
    """Detail page section types."""
    HERO = "hero"
    FEATURES = "features"
    SPECIFICATIONS = "specifications"
    USAGE_SCENARIOS = "usage_scenarios"
    SIZE_CHART = "size_chart"
    BRAND_STORY = "brand_story"
    CTA = "cta"


@dataclass
class FontConfig:
    """Font configuration for text elements."""
    font_path: Optional[str] = None
    size: int = 48
    color: tuple = (255, 255, 255, 255)
    position: str = "bottom"
    stroke_width: int = 2
    stroke_color: tuple = (0, 0, 0, 180)


@dataclass
class DesignTemplate:
    """Design template definition."""
    id: str
    name: str
    style: TemplateStyle
    category: str
    description: str
    size: tuple = (800, 800)
    background_prompt: str = ""
    text_areas: list[dict] = field(default_factory=list)
    font_config: FontConfig = field(default_factory=FontConfig)
    product_position: str = "center"
    product_scale: float = 0.75
    sections: list[DetailSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# -- Main Image Templates by Category --

_MAIN_IMAGE_TEMPLATES: dict[str, list[DesignTemplate]] = {
    "default": [
        DesignTemplate(
            id="main_clean_gradient_01",
            name="Clean Gradient Standard",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="default",
            description="Professional clean gradient background, product centered",
            size=(800, 800),
            background_prompt="Soft pastel gradient background, professional product photography, clean minimalist style",
            product_position="center",
            product_scale=0.75,
        ),
        DesignTemplate(
            id="main_lifestyle_01",
            name="Lifestyle Scene",
            style=TemplateStyle.LIFESTYLE,
            category="default",
            description="Product placed in a lifestyle scene with natural lighting",
            size=(800, 800),
            background_prompt="Warm lifestyle scene, natural lighting, wooden table, green plants, soft bokeh",
            product_position="center",
            product_scale=0.65,
        ),
        DesignTemplate(
            id="main_bold_text_01",
            name="Bold Text Overlay",
            style=TemplateStyle.BOLD_TEXT,
            category="default",
            description="Eye-catching background with bold marketing text",
            size=(800, 800),
            background_prompt="Vibrant colorful background with geometric shapes, modern design, high contrast",
            text_areas=[
                {"position": "top", "max_chars": 12, "purpose": "headline"},
                {"position": "bottom", "max_chars": 20, "purpose": "subtext"},
            ],
            font_config=FontConfig(size=56, color=(255, 255, 255, 255), position="top"),
            product_position="center",
            product_scale=0.6,
        ),
        DesignTemplate(
            id="main_festival_01",
            name="Festival Theme",
            style=TemplateStyle.FESTIVAL_THEME,
            category="default",
            description="Festive celebration theme with golden accents",
            size=(800, 800),
            background_prompt="Festive red and gold background, celebration atmosphere, fireworks, premium luxury feel",
            text_areas=[
                {"position": "top", "max_chars": 8, "purpose": "festival_name"},
            ],
            font_config=FontConfig(size=64, color=(255, 215, 0, 255), position="top"),
            product_position="bottom_center",
            product_scale=0.7,
        ),
    ],
    "clothing": [
        DesignTemplate(
            id="main_clothing_model_01",
            name="Model Lifestyle",
            style=TemplateStyle.LIFESTYLE,
            category="clothing",
            description="Fashion lifestyle scene, model presentation style",
            size=(800, 1000),
            background_prompt="Fashion photography studio, soft directional lighting, neutral gray background, editorial style",
            product_position="center",
            product_scale=0.85,
        ),
        DesignTemplate(
            id="main_clothing_flat_01",
            name="Flat Lay Clean",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="clothing",
            description="Flat lay presentation on clean background",
            size=(800, 800),
            background_prompt="Clean white marble surface, flat lay photography, soft shadows, minimal props",
            product_position="center",
            product_scale=0.8,
        ),
    ],
    "electronics": [
        DesignTemplate(
            id="main_electronics_tech_01",
            name="Tech Dark",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="electronics",
            description="Dark tech-themed background with subtle glow effects",
            size=(800, 800),
            background_prompt="Dark futuristic background, subtle blue glow, tech texture, professional product showcase",
            product_position="center",
            product_scale=0.7,
        ),
        DesignTemplate(
            id="main_electronics_scene_01",
            name="Desk Scene",
            style=TemplateStyle.LIFESTYLE,
            category="electronics",
            description="Modern desk/workspace scene",
            size=(800, 800),
            background_prompt="Modern minimalist desk setup, warm lighting, clean workspace, technology lifestyle",
            product_position="center",
            product_scale=0.65,
        ),
    ],
    "food": [
        DesignTemplate(
            id="main_food_appetizing_01",
            name="Appetizing Close-up",
            style=TemplateStyle.LIFESTYLE,
            category="food",
            description="Appetizing food photography style with warm tones",
            size=(800, 800),
            background_prompt="Rustic wooden table, fresh ingredients scattered, warm natural light, food photography style",
            product_position="center",
            product_scale=0.75,
        ),
    ],
    "beauty": [
        DesignTemplate(
            id="main_beauty_luxury_01",
            name="Luxury Beauty",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="beauty",
            description="Luxurious beauty product presentation",
            size=(800, 800),
            background_prompt="Soft pink and gold gradient, luxury cosmetics background, silk texture, dewdrops, elegant",
            product_position="center",
            product_scale=0.7,
        ),
    ],
}

# -- Detail Page Templates --

_DETAIL_PAGE_TEMPLATES: dict[str, list[DesignTemplate]] = {
    "default": [
        DesignTemplate(
            id="detail_standard_01",
            name="Standard Detail Page",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="default",
            description="Standard detail page with all core sections",
            size=(750, 0),  # Width fixed, height dynamic
            sections=[
                DetailSection.HERO,
                DetailSection.FEATURES,
                DetailSection.SPECIFICATIONS,
                DetailSection.USAGE_SCENARIOS,
                DetailSection.CTA,
            ],
        ),
        DesignTemplate(
            id="detail_premium_01",
            name="Premium Detail Page",
            style=TemplateStyle.LIFESTYLE,
            category="default",
            description="Premium detail page with brand story and full sections",
            size=(750, 0),
            sections=[
                DetailSection.HERO,
                DetailSection.BRAND_STORY,
                DetailSection.FEATURES,
                DetailSection.SPECIFICATIONS,
                DetailSection.USAGE_SCENARIOS,
                DetailSection.SIZE_CHART,
                DetailSection.CTA,
            ],
        ),
    ],
    "clothing": [
        DesignTemplate(
            id="detail_clothing_01",
            name="Clothing Detail Page",
            style=TemplateStyle.LIFESTYLE,
            category="clothing",
            description="Clothing-focused detail page with size chart",
            size=(750, 0),
            sections=[
                DetailSection.HERO,
                DetailSection.FEATURES,
                DetailSection.SIZE_CHART,
                DetailSection.USAGE_SCENARIOS,
                DetailSection.SPECIFICATIONS,
                DetailSection.CTA,
            ],
        ),
    ],
    "electronics": [
        DesignTemplate(
            id="detail_electronics_01",
            name="Electronics Detail Page",
            style=TemplateStyle.CLEAN_GRADIENT,
            category="electronics",
            description="Tech product detail page emphasizing specs",
            size=(750, 0),
            sections=[
                DetailSection.HERO,
                DetailSection.FEATURES,
                DetailSection.SPECIFICATIONS,
                DetailSection.USAGE_SCENARIOS,
                DetailSection.BRAND_STORY,
                DetailSection.CTA,
            ],
        ),
    ],
}


class TemplateManager:
    """Manages design templates for different product categories and use cases."""

    def get_main_image_templates(self, category: str) -> list[DesignTemplate]:
        """Get main image templates for a product category.

        Args:
            category: Product category (e.g., 'clothing', 'electronics', 'food').

        Returns:
            List of applicable design templates. Falls back to default if
            category-specific templates are not available.
        """
        templates = _MAIN_IMAGE_TEMPLATES.get(category, [])
        if not templates:
            templates = _MAIN_IMAGE_TEMPLATES["default"]
            logger.info("No main image templates for category '%s', using defaults", category)
        return templates

    def get_detail_page_templates(self, category: str) -> list[DesignTemplate]:
        """Get detail page templates for a product category.

        Args:
            category: Product category.

        Returns:
            List of applicable detail page templates. Falls back to default
            if category-specific templates are not available.
        """
        templates = _DETAIL_PAGE_TEMPLATES.get(category, [])
        if not templates:
            templates = _DETAIL_PAGE_TEMPLATES["default"]
            logger.info("No detail page templates for category '%s', using defaults", category)
        return templates

    def get_template_by_id(self, template_id: str) -> Optional[DesignTemplate]:
        """Look up a specific template by its ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            The template if found, None otherwise.
        """
        for templates in _MAIN_IMAGE_TEMPLATES.values():
            for t in templates:
                if t.id == template_id:
                    return t
        for templates in _DETAIL_PAGE_TEMPLATES.values():
            for t in templates:
                if t.id == template_id:
                    return t
        return None

    def list_all_templates(self) -> list[DesignTemplate]:
        """List all available templates across categories."""
        all_templates = []
        seen_ids = set()
        for templates in _MAIN_IMAGE_TEMPLATES.values():
            for t in templates:
                if t.id not in seen_ids:
                    all_templates.append(t)
                    seen_ids.add(t.id)
        for templates in _DETAIL_PAGE_TEMPLATES.values():
            for t in templates:
                if t.id not in seen_ids:
                    all_templates.append(t)
                    seen_ids.add(t.id)
        return all_templates

    def get_styles(self) -> list[str]:
        """Return all available style names."""
        return [s.value for s in TemplateStyle]

    def get_detail_sections(self) -> list[str]:
        """Return all available detail page section types."""
        return [s.value for s in DetailSection]
