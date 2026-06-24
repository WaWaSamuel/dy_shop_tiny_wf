"""Image processing pipeline for design asset generation.

Uses Pillow for image manipulation and httpx for AI API calls
(background removal, background generation).
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

TEMP_DIR = Path("/tmp/design_assets")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

AI_API_BASE_URL = os.getenv("AI_IMAGE_API_BASE_URL", "http://ai-image-service:8000")
AI_API_KEY = os.getenv("AI_IMAGE_API_KEY", "")


def _temp_path(suffix: str = ".png") -> str:
    """Generate a unique temporary file path."""
    return str(TEMP_DIR / f"{uuid.uuid4().hex}{suffix}")


class ImagePipeline:
    """Handles all image processing operations for design asset production."""

    def __init__(self, api_base_url: str = AI_API_BASE_URL, api_key: str = AI_API_KEY):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def remove_background(self, image_path: str) -> str:
        """Remove background from product image using AI, returning transparent PNG path.

        Args:
            image_path: Path to the source image.

        Returns:
            Path to the resulting transparent PNG.
        """
        logger.info("Removing background from: %s", image_path)
        output_path = _temp_path(".png")

        try:
            client = await self._get_client()
            with open(image_path, "rb") as f:
                response = await client.post(
                    "/v1/remove-background",
                    files={"image": ("image.png", f, "image/png")},
                )
            response.raise_for_status()

            with open(output_path, "wb") as out:
                out.write(response.content)

            logger.info("Background removed successfully: %s", output_path)
            return output_path

        except httpx.HTTPStatusError as e:
            logger.error("AI background removal API error: %s", e.response.text)
            raise RuntimeError(f"Background removal failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Network error during background removal: %s", str(e))
            raise RuntimeError("Background removal service unavailable") from e

    async def enhance_image(self, image_path: str) -> str:
        """Auto-enhance image: brightness, contrast, color correction, sharpening.

        Args:
            image_path: Path to the source image.

        Returns:
            Path to the enhanced image.
        """
        logger.info("Enhancing image: %s", image_path)
        output_path = _temp_path(".png")

        try:
            img = Image.open(image_path)

            # Auto brightness adjustment
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.05)

            # Auto contrast adjustment
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)

            # Color saturation boost
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.08)

            # Sharpening
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)

            # Slight unsharp mask for detail
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=2))

            img.save(output_path, "PNG", quality=95)
            logger.info("Image enhanced successfully: %s", output_path)
            return output_path

        except Exception as e:
            logger.error("Image enhancement failed: %s", str(e))
            raise RuntimeError(f"Image enhancement failed: {str(e)}") from e

    async def generate_background(
        self, style: str, category: str, size: tuple[int, int] = (800, 800)
    ) -> str:
        """Generate an AI background based on style and product category.

        Args:
            style: Background style (e.g., 'clean_gradient', 'lifestyle').
            category: Product category for context-aware generation.
            size: Output image dimensions (width, height).

        Returns:
            Path to the generated background image.
        """
        logger.info("Generating background: style=%s, category=%s, size=%s", style, category, size)
        output_path = _temp_path(".png")

        prompt = self._build_background_prompt(style, category)

        try:
            client = await self._get_client()
            response = await client.post(
                "/v1/generate-image",
                json={
                    "prompt": prompt,
                    "width": size[0],
                    "height": size[1],
                    "style": style,
                    "category": category,
                },
            )
            response.raise_for_status()

            with open(output_path, "wb") as out:
                out.write(response.content)

            logger.info("Background generated successfully: %s", output_path)
            return output_path

        except httpx.HTTPStatusError as e:
            logger.error("AI background generation API error: %s", e.response.text)
            raise RuntimeError(f"Background generation failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Network error during background generation: %s", str(e))
            raise RuntimeError("Background generation service unavailable") from e

    def _build_background_prompt(self, style: str, category: str) -> str:
        """Build a prompt for background generation based on style and category."""
        style_prompts = {
            "clean_gradient": f"Clean minimalist gradient background suitable for {category} product photography, soft colors, professional e-commerce style",
            "lifestyle": f"Lifestyle scene background for {category}, natural lighting, warm atmosphere, depth of field",
            "bold_text": f"Bold colorful background for {category} product with space for text overlay, high contrast, modern design",
            "festival_theme": f"Festive celebration background for {category}, holiday decorations, warm golden tones, premium feel",
        }
        return style_prompts.get(
            style,
            f"Professional product photography background for {category}, clean, modern, e-commerce style",
        )

    async def composite(
        self,
        foreground_path: str,
        background_path: str,
        position: str = "center",
    ) -> str:
        """Composite foreground product image onto background.

        Args:
            foreground_path: Path to the foreground (transparent PNG cutout).
            background_path: Path to the background image.
            position: Placement position ('center', 'bottom_center', 'left', 'right').

        Returns:
            Path to the composited image.
        """
        logger.info("Compositing: fg=%s, bg=%s, pos=%s", foreground_path, background_path, position)
        output_path = _temp_path(".png")

        try:
            background = Image.open(background_path).convert("RGBA")
            foreground = Image.open(foreground_path).convert("RGBA")

            # Scale foreground to fit within background (80% of smaller dimension)
            bg_w, bg_h = background.size
            fg_w, fg_h = foreground.size
            max_dim = int(min(bg_w, bg_h) * 0.8)
            scale = min(max_dim / fg_w, max_dim / fg_h)
            if scale < 1.0:
                new_size = (int(fg_w * scale), int(fg_h * scale))
                foreground = foreground.resize(new_size, Image.LANCZOS)
                fg_w, fg_h = foreground.size

            # Calculate position
            offset = self._calculate_position(position, bg_w, bg_h, fg_w, fg_h)

            # Composite using alpha channel
            background.paste(foreground, offset, foreground)
            background.save(output_path, "PNG")

            logger.info("Composite created: %s", output_path)
            return output_path

        except Exception as e:
            logger.error("Compositing failed: %s", str(e))
            raise RuntimeError(f"Image compositing failed: {str(e)}") from e

    def _calculate_position(
        self, position: str, bg_w: int, bg_h: int, fg_w: int, fg_h: int
    ) -> tuple[int, int]:
        """Calculate paste offset based on position string."""
        positions = {
            "center": ((bg_w - fg_w) // 2, (bg_h - fg_h) // 2),
            "bottom_center": ((bg_w - fg_w) // 2, bg_h - fg_h - int(bg_h * 0.05)),
            "left": (int(bg_w * 0.1), (bg_h - fg_h) // 2),
            "right": (bg_w - fg_w - int(bg_w * 0.1), (bg_h - fg_h) // 2),
        }
        return positions.get(position, positions["center"])

    async def add_text_overlay(
        self,
        image_path: str,
        text: str,
        font_config: Optional[dict] = None,
    ) -> str:
        """Add marketing text overlay to an image.

        Args:
            image_path: Path to the source image.
            text: Text content to overlay.
            font_config: Optional font configuration dict with keys:
                - font_path: str (path to .ttf font file)
                - size: int (font size in pixels)
                - color: tuple (RGBA color)
                - position: str ('top', 'bottom', 'center')
                - stroke_width: int
                - stroke_color: tuple (RGBA)

        Returns:
            Path to the image with text overlay.
        """
        logger.info("Adding text overlay: %s", text[:50])
        output_path = _temp_path(".png")

        config = {
            "font_path": None,
            "size": 48,
            "color": (255, 255, 255, 255),
            "position": "bottom",
            "stroke_width": 2,
            "stroke_color": (0, 0, 0, 180),
        }
        if font_config:
            config.update(font_config)

        try:
            img = Image.open(image_path).convert("RGBA")
            txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(txt_layer)

            # Load font
            try:
                if config["font_path"] and os.path.exists(config["font_path"]):
                    font = ImageFont.truetype(config["font_path"], config["size"])
                else:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["size"])
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Calculate text position
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            img_w, img_h = img.size

            if config["position"] == "top":
                x = (img_w - text_w) // 2
                y = int(img_h * 0.08)
            elif config["position"] == "center":
                x = (img_w - text_w) // 2
                y = (img_h - text_h) // 2
            else:  # bottom
                x = (img_w - text_w) // 2
                y = img_h - text_h - int(img_h * 0.08)

            # Draw text with stroke
            draw.text(
                (x, y),
                text,
                font=font,
                fill=config["color"],
                stroke_width=config["stroke_width"],
                stroke_fill=config["stroke_color"],
            )

            # Merge layers
            result = Image.alpha_composite(img, txt_layer)
            result.save(output_path, "PNG")

            logger.info("Text overlay added: %s", output_path)
            return output_path

        except Exception as e:
            logger.error("Text overlay failed: %s", str(e))
            raise RuntimeError(f"Text overlay failed: {str(e)}") from e

    async def create_long_image(self, sections: list[str]) -> str:
        """Stitch multiple image sections vertically to create a detail page long image.

        Args:
            sections: List of file paths to section images (in order top to bottom).

        Returns:
            Path to the stitched long image.
        """
        logger.info("Creating long image from %d sections", len(sections))
        output_path = _temp_path(".png")

        if not sections:
            raise ValueError("At least one section image is required")

        try:
            images = [Image.open(s).convert("RGBA") for s in sections]

            # Normalize all sections to the same width (use first section's width)
            target_width = images[0].width
            resized = []
            for img in images:
                if img.width != target_width:
                    ratio = target_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((target_width, new_height), Image.LANCZOS)
                resized.append(img)

            # Calculate total height
            total_height = sum(img.height for img in resized)

            # Create canvas and paste sections
            canvas = Image.new("RGBA", (target_width, total_height), (255, 255, 255, 255))
            y_offset = 0
            for img in resized:
                canvas.paste(img, (0, y_offset), img)
                y_offset += img.height

            canvas.save(output_path, "PNG")
            logger.info("Long image created: %s (%dx%d)", output_path, target_width, total_height)
            return output_path

        except Exception as e:
            logger.error("Long image creation failed: %s", str(e))
            raise RuntimeError(f"Long image creation failed: {str(e)}") from e
