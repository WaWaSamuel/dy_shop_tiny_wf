"""Design assets router placeholder."""

from fastapi import APIRouter

router = APIRouter()

_TASKS = [
    {
        "id": "1",
        "product_id": "p1",
        "product_name": "Summer Floral Dress",
        "task_type": "main_image",
        "style_template": "Clean Minimal",
        "status": "completed",
        "thumbnail_url": None,
        "output_urls": ["/design-output-1.jpg", "/design-output-2.jpg"],
        "created_at": "2024-06-15T08:00:00Z",
    },
    {
        "id": "2",
        "product_id": "p2",
        "product_name": "Casual Denim Jacket",
        "task_type": "detail_page",
        "style_template": "Lifestyle Scene",
        "status": "generating",
        "thumbnail_url": None,
        "output_urls": [],
        "created_at": "2024-06-15T09:30:00Z",
    },
]

_TEMPLATES = [
    {"id": "clean-minimal", "name": "Clean Minimal", "preview_url": "/template-1.jpg", "task_type": "main_image"},
    {"id": "lifestyle-scene", "name": "Lifestyle Scene", "preview_url": "/template-2.jpg", "task_type": "detail_page"},
]


@router.get("/")
async def list_design_assets() -> dict[str, str]:
    """List generated design assets."""
    return {"status": "ok"}


@router.get("/tasks")
async def list_design_tasks(status: str | None = None) -> dict[str, object]:
    """List design tasks."""
    items = _TASKS if not status else [item for item in _TASKS if item["status"] == status]
    return {"items": items, "total": len(items)}


@router.post("/tasks")
async def create_design_task(payload: dict[str, str]) -> dict[str, object]:
    """Pretend to create a design task."""
    return {
        "id": "new-task",
        "product_id": payload.get("product_id", ""),
        "product_name": "New Design Task",
        "task_type": payload.get("task_type", "main_image"),
        "style_template": payload.get("style_template", "Clean Minimal"),
        "status": "queued",
        "thumbnail_url": None,
        "output_urls": [],
        "created_at": "2024-06-15T12:45:00Z",
    }


@router.get("/tasks/{task_id}")
async def get_design_task(task_id: str) -> dict[str, object]:
    """Return a single design task."""
    for task in _TASKS:
        if task["id"] == task_id:
            return task
    return {
        "id": task_id,
        "product_id": "",
        "product_name": "Unknown Task",
        "task_type": "main_image",
        "style_template": "Clean Minimal",
        "status": "queued",
        "thumbnail_url": None,
        "output_urls": [],
        "created_at": "2024-06-15T12:45:00Z",
    }


@router.post("/tasks/{task_id}/regenerate")
async def regenerate_design_task(task_id: str) -> dict[str, str]:
    """Pretend to regenerate a task."""
    return {"id": task_id, "status": "generating"}


@router.get("/templates")
async def list_design_templates() -> dict[str, object]:
    """List design templates."""
    return {"items": _TEMPLATES}
