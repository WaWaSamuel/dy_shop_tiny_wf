"""Design Asset Service - orchestrates the full design asset generation pipeline.

Coordinates image pipeline, content generation, template management, and OSS upload
to produce main images, detail pages, and promotional assets for products.
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

from .content_generator import DesignContentGenerator
from .image_pipeline import ImagePipeline
from .templates import TemplateManager, TemplateStyle

logger = logging.getLogger(__name__)

OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "https://oss.example.com")
OSS_BUCKET = os.getenv("OSS_BUCKET", "design-assets")
OSS_ACCESS_KEY = os.getenv("OSS_ACCESS_KEY", "")
OSS_SECRET_KEY = os.getenv("OSS_SECRET_KEY", "")


class TaskType(str, Enum):
    """Design task types."""
    MAIN_IMAGE = "main_image"
    DETAIL_PAGE = "detail_page"
    SCENE_IMAGE = "scene_image"
    WHITE_BG = "white_bg"
    PROMOTIONAL_BANNER = "promotional_banner"


class TaskStatus(str, Enum):
    """Design task statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DesignTask:
    """Represents a design generation task."""
    id: str
    product_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    input_images: list[str] = field(default_factory=list)
    output_images: list[str] = field(default_factory=list)
    style_template: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


# In-memory task store (replace with database in production)
_task_store: dict[str, DesignTask] = {}


class DesignAssetService:
    """Orchestrates design asset generation for products.

    Manages the full pipeline from source image input to final uploaded assets,
    coordinating background removal, AI generation, compositing, and upload.
    """

    def __init__(self):
        self.pipeline = ImagePipeline()
        self.templates = TemplateManager()
        self.content_gen = DesignContentGenerator()

    async def close(self):
        """Cleanup resources."""
        await self.pipeline.close()
        await self.content_gen.close()

    def create_design_task(
        self,
        product_id: str,
        task_type: str,
        input_images: list[str],
        style_template: Optional[str] = None,
    ) -> DesignTask:
        """Create a new design generation task.

        Args:
            product_id: ID of the product to generate assets for.
            task_type: Type of design task (main_image, detail_page, etc.).
            input_images: List of source image paths/URLs.
            style_template: Optional template ID to use.

        Returns:
            The created DesignTask instance.
        """
        task = DesignTask(
            id=uuid.uuid4().hex,
            product_id=product_id,
            task_type=TaskType(task_type),
            input_images=input_images,
            style_template=style_template,
        )
        _task_store[task.id] = task
        logger.info("Created design task: %s (type=%s, product=%s)", task.id, task_type, product_id)
        return task

    async def process_task(self, task_id: str) -> DesignTask:
        """Process a design task through the full pipeline.

        Pipeline: remove background -> generate based on task type -> upload results.

        Args:
            task_id: ID of the task to process.

        Returns:
            The updated DesignTask with results.

        Raises:
            ValueError: If task_id is not found.
            RuntimeError: If processing fails.
        """
        task = _task_store.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.PROCESSING
        logger.info("Processing task: %s (type=%s)", task_id, task.task_type)

        try:
            # Step 1: Remove background from input images
            cutouts = []
            for img_path in task.input_images:
                cutout = await self.pipeline.remove_background(img_path)
                cutout = await self.pipeline.enhance_image(cutout)
                cutouts.append(cutout)

            if not cutouts:
                raise RuntimeError("No valid cutouts produced from input images")

            primary_cutout = cutouts[0]

            # Step 2: Generate based on task type
            if task.task_type == TaskType.MAIN_IMAGE:
                style = task.style_template or TemplateStyle.CLEAN_GRADIENT.value
                output_paths = await self.generate_main_images(primary_cutout, style, count=5)

            elif task.task_type == TaskType.DETAIL_PAGE:
                product_info = task.metadata.get("product_info", {"name": "Product"})
                category = task.metadata.get("category", "default")
                output_path = await self.generate_detail_page(product_info, primary_cutout, category)
                output_paths = [output_path]

            elif task.task_type == TaskType.SCENE_IMAGE:
                category = task.metadata.get("category", "default")
                output_paths = await self.generate_scene_images(primary_cutout, category, count=3)

            elif task.task_type == TaskType.WHITE_BG:
                output_paths = []
                for img_path in task.input_images:
                    white_bg = await self.generate_white_bg(img_path)
                    output_paths.append(white_bg)

            else:
                raise ValueError(f"Unsupported task type: {task.task_type}")

            # Step 3: Upload to OSS
            uploaded_urls = []
            for path in output_paths:
                url = await self.upload_to_oss(path)
                uploaded_urls.append(url)

            task.output_images = uploaded_urls
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            logger.info("Task completed: %s (%d outputs)", task_id, len(uploaded_urls))

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error("Task failed: %s - %s", task_id, str(e))
            raise

        return task

    async def generate_main_images(
        self, product_cutout: str, style: str, count: int = 5
    ) -> list[str]:
        """Generate main product images with AI backgrounds and text overlay.

        Args:
            product_cutout: Path to the background-removed product image.
            style: Style template name (e.g., 'clean_gradient', 'lifestyle').
            count: Number of variations to generate.

        Returns:
            List of paths to generated main images.
        """
        logger.info("Generating %d main images with style: %s", count, style)
        results = []

        templates = self.templates.get_main_image_templates("default")
        # Filter templates matching the requested style if possible
        style_templates = [t for t in templates if t.style.value == style]
        if not style_templates:
            style_templates = templates

        for i in range(count):
            template = style_templates[i % len(style_templates)]

            # Generate background
            bg_path = await self.pipeline.generate_background(
                style=template.style.value,
                category=template.category,
                size=template.size,
            )

            # Composite product onto background
            composite_path = await self.pipeline.composite(
                foreground_path=product_cutout,
                background_path=bg_path,
                position=template.product_position,
            )

            # Add text overlay if template has text areas
            if template.text_areas:
                text = template.text_areas[0].get("purpose", "")
                composite_path = await self.pipeline.add_text_overlay(
                    image_path=composite_path,
                    text=text,
                    font_config={
                        "size": template.font_config.size,
                        "color": template.font_config.color,
                        "position": template.font_config.position,
                    },
                )

            results.append(composite_path)

        logger.info("Generated %d main images", len(results))
        return results

    async def generate_detail_page(
        self, product_info: dict, cutout: str, category: str
    ) -> str:
        """Generate a template-based detail page long image.

        Args:
            product_info: Product information dictionary.
            cutout: Path to the background-removed product cutout.
            category: Product category.

        Returns:
            Path to the generated detail page long image.
        """
        logger.info("Generating detail page for category: %s", category)

        # Get template
        templates = self.templates.get_detail_page_templates(category)
        template = templates[0]

        # Generate section content
        sections_content = await self.content_gen.generate_detail_sections(product_info, category)

        # Generate section images
        section_images = []

        for section in template.sections:
            if section.value == "hero":
                # Hero: product on styled background with title
                bg = await self.pipeline.generate_background("clean_gradient", category, (750, 500))
                hero = await self.pipeline.composite(cutout, bg, "center")
                title = sections_content.get("hero", {}).get("title", product_info.get("name", ""))
                hero = await self.pipeline.add_text_overlay(hero, title, {"position": "bottom", "size": 42})
                section_images.append(hero)

            elif section.value == "features":
                # Features section with selling points
                bg = await self.pipeline.generate_background("clean_gradient", category, (750, 600))
                features = sections_content.get("features", [])
                text = " | ".join(f.get("title", "") for f in features[:4]) if features else "Premium Quality"
                featured = await self.pipeline.add_text_overlay(bg, text, {"position": "center", "size": 36})
                section_images.append(featured)

            elif section.value == "specifications":
                bg = await self.pipeline.generate_background("clean_gradient", category, (750, 400))
                specs = sections_content.get("specifications", [])
                text = "\n".join(f"{s['label']}: {s['value']}" for s in specs[:5]) if specs else "Specifications"
                spec_img = await self.pipeline.add_text_overlay(bg, text, {"position": "center", "size": 28})
                section_images.append(spec_img)

            elif section.value == "usage_scenarios":
                bg = await self.pipeline.generate_background("lifestyle", category, (750, 500))
                scene = await self.pipeline.composite(cutout, bg, "center")
                section_images.append(scene)

            elif section.value == "size_chart":
                bg = await self.pipeline.generate_background("clean_gradient", category, (750, 400))
                section_images.append(bg)

            elif section.value == "brand_story":
                bg = await self.pipeline.generate_background("lifestyle", category, (750, 400))
                story = sections_content.get("brand_story", {})
                text = story.get("text", "Our story")[:100]
                story_img = await self.pipeline.add_text_overlay(bg, text, {"position": "center", "size": 30})
                section_images.append(story_img)

            elif section.value == "cta":
                bg = await self.pipeline.generate_background("bold_text", category, (750, 300))
                cta = sections_content.get("cta", {})
                text = cta.get("headline", "Order Now")
                cta_img = await self.pipeline.add_text_overlay(bg, text, {"position": "center", "size": 48})
                section_images.append(cta_img)

        # Stitch sections into long image
        long_image = await self.pipeline.create_long_image(section_images)
        logger.info("Detail page generated: %s", long_image)
        return long_image

    async def generate_scene_images(
        self, product_cutout: str, category: str, count: int = 3
    ) -> list[str]:
        """Generate product images in realistic scene settings.

        Args:
            product_cutout: Path to the background-removed product image.
            category: Product category for scene context.
            count: Number of scene variations to generate.

        Returns:
            List of paths to generated scene images.
        """
        logger.info("Generating %d scene images for category: %s", count, category)
        results = []

        for i in range(count):
            # Generate scene background
            scene_bg = await self.pipeline.generate_background(
                style="lifestyle",
                category=category,
                size=(800, 800),
            )

            # Composite product into scene
            positions = ["center", "left", "right"]
            position = positions[i % len(positions)]
            scene = await self.pipeline.composite(product_cutout, scene_bg, position)
            results.append(scene)

        logger.info("Generated %d scene images", len(results))
        return results

    async def generate_white_bg(self, product_photo: str) -> str:
        """Generate a white background product image.

        Removes original background and fills with pure white.

        Args:
            product_photo: Path to the original product photo.

        Returns:
            Path to the white-background product image.
        """
        logger.info("Generating white background image from: %s", product_photo)

        # Remove background
        cutout = await self.pipeline.remove_background(product_photo)

        # Create white background at same size
        from PIL import Image
        fg = Image.open(cutout).convert("RGBA")
        white_bg_path = self.pipeline._temp_path(".png") if hasattr(self.pipeline, '_temp_path') else f"/tmp/design_assets/{uuid.uuid4().hex}.png"

        white_bg = Image.new("RGBA", fg.size, (255, 255, 255, 255))
        white_bg.paste(fg, (0, 0), fg)
        white_bg.save(white_bg_path, "PNG")

        logger.info("White background image created: %s", white_bg_path)
        return white_bg_path

    async def upload_to_oss(self, local_path: str) -> str:
        """Upload a generated asset to cloud storage (OSS).

        Args:
            local_path: Path to the local file to upload.

        Returns:
            Public URL of the uploaded file.

        Raises:
            RuntimeError: If upload fails.
        """
        logger.info("Uploading to OSS: %s", local_path)

        filename = os.path.basename(local_path)
        object_key = f"design-assets/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}_{filename}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                with open(local_path, "rb") as f:
                    response = await client.put(
                        f"{OSS_ENDPOINT}/{OSS_BUCKET}/{object_key}",
                        content=f.read(),
                        headers={
                            "Content-Type": "image/png",
                            "x-oss-access-key": OSS_ACCESS_KEY,
                            "x-oss-secret-key": OSS_SECRET_KEY,
                        },
                    )
                response.raise_for_status()

            url = f"{OSS_ENDPOINT}/{OSS_BUCKET}/{object_key}"
            logger.info("Uploaded to OSS: %s", url)
            return url

        except httpx.HTTPStatusError as e:
            logger.error("OSS upload failed: %s", e.response.text)
            raise RuntimeError(f"OSS upload failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Network error during OSS upload: %s", str(e))
            raise RuntimeError("OSS service unavailable") from e

    def get_task(self, task_id: str) -> Optional[DesignTask]:
        """Retrieve a task by ID."""
        return _task_store.get(task_id)

    def list_tasks(
        self,
        product_id: Optional[str] = None,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[DesignTask]:
        """List tasks with optional filters.

        Args:
            product_id: Filter by product ID.
            task_type: Filter by task type.
            status: Filter by status.

        Returns:
            List of matching tasks.
        """
        tasks = list(_task_store.values())

        if product_id:
            tasks = [t for t in tasks if t.product_id == product_id]
        if task_type:
            tasks = [t for t in tasks if t.task_type.value == task_type]
        if status:
            tasks = [t for t in tasks if t.status.value == status]

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
