import enum
import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DesignTaskType(str, enum.Enum):
    MAIN_IMAGE = "main_image"
    DETAIL_PAGE = "detail_page"
    SCENE_IMAGE = "scene_image"
    WHITE_BG = "white_bg"
    BANNER = "banner"


class DesignTaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DesignTemplateType(str, enum.Enum):
    MAIN_IMAGE = "main_image"
    DETAIL_PAGE = "detail_page"
    BANNER = "banner"


class DesignTask(Base):
    __tablename__ = "design_tasks"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_type: Mapped[DesignTaskType] = mapped_column(String(16), nullable=False)
    status: Mapped[DesignTaskStatus] = mapped_column(
        String(16), nullable=False, default=DesignTaskStatus.PENDING
    )
    input_images: Mapped[list[Any]] = mapped_column(JSON, default=list)
    output_images: Mapped[list[Any]] = mapped_column(JSON, default=list)
    style_template: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    generation_params: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_design_tasks_product_id", "product_id"),
        Index("ix_design_tasks_status", "status"),
        Index("ix_design_tasks_task_type", "task_type"),
    )


class DesignTemplate(Base):
    __tablename__ = "design_templates"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    template_type: Mapped[DesignTemplateType] = mapped_column(
        String(16), nullable=False
    )
    style_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    preview_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    __table_args__ = (
        Index("ix_design_templates_category", "category"),
        Index("ix_design_templates_template_type", "template_type"),
    )
