"""FastAPI router for the Design Asset Production module.

Provides REST API endpoints for creating, managing, and downloading
design generation tasks and their outputs.
"""

import io
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .service import DesignAssetService, DesignTask, TaskStatus, TaskType
from .tasks import process_design_task_async, regenerate_task
from .templates import TemplateManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/design", tags=["design-assets"])

# Service instances (in production, use dependency injection)
_service = DesignAssetService()
_template_manager = TemplateManager()

UPLOAD_DIR = "/tmp/design_assets/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# -- Request/Response Models --


class CreateTaskRequest(BaseModel):
    """Request body for creating a design task."""
    product_id: str = Field(..., description="Product ID to generate assets for")
    task_type: str = Field(..., description="Task type: main_image, detail_page, scene_image, white_bg")
    input_images: list[str] = Field(..., description="List of source image paths or URLs")
    style_template: Optional[str] = Field(None, description="Optional style template ID")
    metadata: Optional[dict] = Field(None, description="Additional metadata (product_info, category, etc.)")


class RegenerateRequest(BaseModel):
    """Request body for regenerating a task."""
    style_template: Optional[str] = Field(None, description="New style template")
    count: Optional[int] = Field(None, description="Number of outputs to generate")
    metadata: Optional[dict] = Field(None, description="Additional metadata overrides")


class TaskResponse(BaseModel):
    """Response model for a design task."""
    id: str
    product_id: str
    task_type: str
    status: str
    input_images: list[str]
    output_images: list[str]
    style_template: Optional[str]
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]

    @classmethod
    def from_task(cls, task: DesignTask) -> "TaskResponse":
        return cls(
            id=task.id,
            product_id=task.product_id,
            task_type=task.task_type.value,
            status=task.status.value,
            input_images=task.input_images,
            output_images=task.output_images,
            style_template=task.style_template,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )


class TemplateResponse(BaseModel):
    """Response model for a design template."""
    id: str
    name: str
    style: str
    category: str
    description: str
    size: list[int]


class TaskListResponse(BaseModel):
    """Response for listing tasks."""
    total: int
    tasks: list[TaskResponse]


class TemplateListResponse(BaseModel):
    """Response for listing templates."""
    total: int
    templates: list[TemplateResponse]
    styles: list[str]
    detail_sections: list[str]


# -- Endpoints --


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_design_task(request: CreateTaskRequest):
    """Create a new design generation task.

    Creates the task and dispatches it for asynchronous processing via Celery.
    """
    try:
        task = _service.create_design_task(
            product_id=request.product_id,
            task_type=request.task_type,
            input_images=request.input_images,
            style_template=request.style_template,
        )

        # Store additional metadata
        if request.metadata:
            task.metadata.update(request.metadata)

        # Dispatch async processing
        process_design_task_async.delay(task.id)

        logger.info("Design task created and dispatched: %s", task.id)
        return TaskResponse.from_task(task)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create design task: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to create design task")


@router.get("/tasks", response_model=TaskListResponse)
async def list_design_tasks(
    product_id: Optional[str] = Query(None, description="Filter by product ID"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List design tasks with optional filters."""
    tasks = _service.list_tasks(
        product_id=product_id,
        task_type=task_type,
        status=status,
    )

    total = len(tasks)
    tasks_page = tasks[offset: offset + limit]

    return TaskListResponse(
        total=total,
        tasks=[TaskResponse.from_task(t) for t in tasks_page],
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_design_task(task_id: str):
    """Get details of a specific design task including output images."""
    task = _service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return TaskResponse.from_task(task)


@router.post("/tasks/{task_id}/regenerate", response_model=TaskResponse)
async def regenerate_design_task(task_id: str, request: RegenerateRequest):
    """Regenerate a design task with new parameters.

    Dispatches regeneration asynchronously and returns the updated task.
    """
    task = _service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    params = {}
    if request.style_template:
        params["style_template"] = request.style_template
    if request.count:
        params["count"] = request.count
    if request.metadata:
        params["metadata"] = request.metadata

    # Dispatch async regeneration
    regenerate_task.delay(task_id, params)

    # Update local state to reflect pending regeneration
    task.status = TaskStatus.PENDING
    logger.info("Regeneration dispatched for task: %s", task_id)

    return TaskResponse.from_task(task)


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """List available design templates."""
    if category:
        main_templates = _template_manager.get_main_image_templates(category)
        detail_templates = _template_manager.get_detail_page_templates(category)
        all_templates = main_templates + detail_templates
    else:
        all_templates = _template_manager.list_all_templates()

    template_responses = [
        TemplateResponse(
            id=t.id,
            name=t.name,
            style=t.style.value,
            category=t.category,
            description=t.description,
            size=list(t.size),
        )
        for t in all_templates
    ]

    return TemplateListResponse(
        total=len(template_responses),
        templates=template_responses,
        styles=_template_manager.get_styles(),
        detail_sections=_template_manager.get_detail_sections(),
    )


@router.post("/upload")
async def upload_source_photos(files: list[UploadFile] = File(...)):
    """Upload source product photos for design generation.

    Accepts multiple image files and stores them for use as design task inputs.

    Returns:
        List of uploaded file paths that can be used as input_images in task creation.
    """
    uploaded_paths = []

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is not a valid image",
            )

        # Generate unique filename
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        # Save file
        try:
            content = await file.read()
            with open(filepath, "wb") as f:
                f.write(content)
            uploaded_paths.append(filepath)
            logger.info("Uploaded source photo: %s", filepath)
        except Exception as e:
            logger.error("Failed to upload file %s: %s", file.filename, str(e))
            raise HTTPException(status_code=500, detail=f"Failed to upload: {file.filename}")

    return {
        "uploaded": len(uploaded_paths),
        "paths": uploaded_paths,
    }


@router.get("/tasks/{task_id}/download")
async def download_generated_assets(task_id: str):
    """Download all generated assets for a task as a zip file.

    Returns a zip archive containing all output images from a completed task.
    """
    task = _service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not completed (status: {task.status.value})",
        )

    if not task.output_images:
        raise HTTPException(status_code=404, detail="No output images available")

    # Create zip in memory
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, image_url in enumerate(task.output_images):
                # For local paths, read directly; for URLs, the path component is used
                # In production, download from OSS; here we handle local paths
                local_path = image_url
                if os.path.exists(local_path):
                    ext = os.path.splitext(local_path)[1] or ".png"
                    zf.write(local_path, f"{task.task_type.value}_{i+1:02d}{ext}")
                else:
                    # If it's a URL, add a placeholder reference
                    zf.writestr(
                        f"{task.task_type.value}_{i+1:02d}.url",
                        f"[InternetShortcut]\nURL={image_url}\n",
                    )
    except Exception as e:
        logger.error("Failed to create zip for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to create download archive")

    zip_buffer.seek(0)
    filename = f"design_assets_{task.product_id}_{task.task_type.value}_{task_id[:8]}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
