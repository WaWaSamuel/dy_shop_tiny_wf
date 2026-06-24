"""Design Asset Production Module.

Generates product main images, detail pages, and promotional banners using AI,
reducing per-product design cost to near-zero and turnaround to under 10 minutes.
"""

from .service import DesignAssetService
from .image_pipeline import ImagePipeline
from .templates import TemplateManager, DesignTemplate
from .content_generator import DesignContentGenerator
from .tasks import process_design_task_async, batch_generate_assets_task, regenerate_task
from .router import router as design_router

__all__ = [
    "DesignAssetService",
    "ImagePipeline",
    "TemplateManager",
    "DesignTemplate",
    "DesignContentGenerator",
    "process_design_task_async",
    "batch_generate_assets_task",
    "regenerate_task",
    "design_router",
]
