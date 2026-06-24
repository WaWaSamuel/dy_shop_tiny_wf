"""Image processing utilities for 抖店 product listings.

Handles validation, resizing, and compression of product images
to meet 抖店 platform requirements before upload.
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# 抖店 image requirements
ALLOWED_FORMATS = {"JPEG", "PNG"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MIN_DIMENSION = 600
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
PREFERRED_RATIO = 1.0  # 1:1 square


@dataclass
class ValidationResult:
    """Result of image validation against 抖店 requirements."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    format: str = ""


class ImageProcessor:
    """Processes product images for 抖店 upload compliance.

    Validates dimensions, format, and file size. Provides auto-resize
    and compression to meet platform requirements.
    """

    def __init__(self, output_dir: str | None = None) -> None:
        """Initialize the image processor.

        Args:
            output_dir: Directory for processed images. Uses temp dir if None.
        """
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="douyin_images_")
        os.makedirs(self.output_dir, exist_ok=True)

    def validate_image(self, image_path: str) -> ValidationResult:
        """Validate an image against 抖店 requirements.

        Checks:
        - Format: JPG or PNG
        - Minimum dimensions: 600x600 pixels
        - Maximum file size: 5MB
        - Aspect ratio: 1:1 (warns if not square)

        Args:
            image_path: Path to the image file.

        Returns:
            ValidationResult with status and any issues found.
        """
        errors: list[str] = []
        warnings: list[str] = []

        path = Path(image_path)

        # Check file exists
        if not path.exists():
            return ValidationResult(
                valid=False,
                errors=["File does not exist"],
                warnings=[],
            )

        # Check extension
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            errors.append(
                f"Invalid format '{path.suffix}'. Allowed: JPG, PNG"
            )

        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            errors.append(
                f"File size {size_mb:.1f}MB exceeds maximum {MAX_FILE_SIZE_MB}MB"
            )

        # Open and check dimensions
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                img_format = img.format or ""

                if img_format not in ALLOWED_FORMATS:
                    errors.append(
                        f"Image format '{img_format}' not supported. Use JPG or PNG."
                    )

                if width < MIN_DIMENSION or height < MIN_DIMENSION:
                    errors.append(
                        f"Image dimensions {width}x{height} below minimum "
                        f"{MIN_DIMENSION}x{MIN_DIMENSION}"
                    )

                # Check aspect ratio
                ratio = width / height if height > 0 else 0
                if abs(ratio - PREFERRED_RATIO) > 0.05:
                    warnings.append(
                        f"Image aspect ratio {ratio:.2f}:1 is not 1:1. "
                        "Square images are recommended for best display."
                    )

                return ValidationResult(
                    valid=len(errors) == 0,
                    errors=errors,
                    warnings=warnings,
                    width=width,
                    height=height,
                    file_size_bytes=file_size,
                    format=img_format,
                )

        except Exception as e:
            errors.append(f"Failed to open image: {e}")
            return ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                file_size_bytes=file_size,
            )

    def resize_image(
        self,
        image_path: str,
        target_size: tuple[int, int] = (800, 800),
    ) -> str:
        """Resize an image while maintaining aspect ratio.

        The image is resized to fit within the target dimensions and then
        placed on a white background of exactly target_size for a 1:1 ratio.

        Args:
            image_path: Path to the source image.
            target_size: Target dimensions as (width, height).

        Returns:
            Path to the resized image file.
        """
        path = Path(image_path)
        output_path = os.path.join(
            self.output_dir,
            f"{path.stem}_resized{path.suffix}",
        )

        with Image.open(image_path) as img:
            # Convert RGBA to RGB if necessary (for JPEG compatibility)
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Create square canvas with white background
            canvas = Image.new("RGB", target_size, (255, 255, 255))
            offset_x = (target_size[0] - img.width) // 2
            offset_y = (target_size[1] - img.height) // 2
            canvas.paste(img, (offset_x, offset_y))

            # Determine format from extension
            save_format = "JPEG" if path.suffix.lower() in (".jpg", ".jpeg") else "PNG"
            canvas.save(output_path, format=save_format, quality=95)

        logger.info(
            "Resized image '%s' to %dx%d -> '%s'",
            image_path,
            target_size[0],
            target_size[1],
            output_path,
        )
        return output_path

    def compress_image(
        self,
        image_path: str,
        max_size_mb: float = 5.0,
    ) -> str:
        """Compress an image to fit within the maximum file size.

        Uses progressive quality reduction for JPEG or quantization for PNG.

        Args:
            image_path: Path to the source image.
            max_size_mb: Maximum allowed file size in megabytes.

        Returns:
            Path to the compressed image file.
        """
        max_size_bytes = int(max_size_mb * 1024 * 1024)
        path = Path(image_path)

        # If already within limits, return as-is
        if path.stat().st_size <= max_size_bytes:
            logger.debug("Image '%s' already within size limit", image_path)
            return image_path

        output_path = os.path.join(
            self.output_dir,
            f"{path.stem}_compressed.jpg",
        )

        with Image.open(image_path) as img:
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Progressive quality reduction
            quality = 95
            while quality >= 30:
                img.save(output_path, format="JPEG", quality=quality, optimize=True)

                if os.path.getsize(output_path) <= max_size_bytes:
                    logger.info(
                        "Compressed image '%s' at quality=%d (%.1fMB)",
                        image_path,
                        quality,
                        os.path.getsize(output_path) / (1024 * 1024),
                    )
                    return output_path

                quality -= 5

            # If still too large after quality reduction, resize
            scale_factor = 0.8
            while os.path.getsize(output_path) > max_size_bytes and scale_factor > 0.3:
                new_size = (
                    int(img.width * scale_factor),
                    int(img.height * scale_factor),
                )
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
                resized.save(output_path, format="JPEG", quality=70, optimize=True)
                scale_factor -= 0.1

            logger.info(
                "Compressed image '%s' to %.1fMB (scale=%.1f)",
                image_path,
                os.path.getsize(output_path) / (1024 * 1024),
                scale_factor + 0.1,
            )
            return output_path
