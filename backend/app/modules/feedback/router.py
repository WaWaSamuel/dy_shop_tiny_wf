"""FastAPI router for the Customer Feedback Management module.

Provides REST endpoints for listing, filtering, approving, and replying
to feedback events, plus knowledge base management and statistics.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.modules.feedback.schemas import (
    FeedbackEvent,
    FeedbackSource,
    FeedbackStatus,
    FeedbackType,
    KBEntry,
)
from app.modules.feedback.service import FeedbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Module-level service instance (in production, use dependency injection)
_service = FeedbackService()


# --- Request/Response models ---


class ApproveRequest(BaseModel):
    """Request body for approving an auto-generated reply."""

    approve: bool = True
    edited_reply: str | None = None


class ManualReplyRequest(BaseModel):
    """Request body for submitting a manual reply."""

    content: str = Field(..., min_length=1, max_length=2000)
    channel: FeedbackSource | None = None


class KBEntryCreateRequest(BaseModel):
    """Request body for adding a knowledge base entry."""

    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=2000)
    category: str = ""
    product_id: str = ""


class FeedbackListResponse(BaseModel):
    """Response for listing feedback events."""

    total: int
    items: list[FeedbackEvent]


class StatsResponse(BaseModel):
    """Response for feedback statistics."""

    total_events: int
    responded_count: int = 0
    auto_reply_rate: float
    avg_response_time_seconds: float
    sentiment_breakdown: dict[str, int]
    type_breakdown: dict[str, int]
    status_breakdown: dict[str, int]


# --- Endpoints ---


@router.get("/", response_model=FeedbackListResponse)
async def list_feedback_events(
    status: FeedbackStatus | None = Query(None, description="Filter by status"),
    feedback_type: FeedbackType | None = Query(None, alias="type", description="Filter by type"),
    source: FeedbackSource | None = Query(None, description="Filter by source channel"),
    min_urgency: int | None = Query(None, ge=1, le=5, description="Minimum urgency score"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
) -> FeedbackListResponse:
    """List feedback events with optional filters.

    Supports filtering by status, type, source channel, and minimum urgency.
    Results are sorted by received time (most recent first).
    """
    events = _service.list_events(
        status=status,
        feedback_type=feedback_type,
        source=source,
        min_urgency=min_urgency,
        offset=offset,
        limit=limit,
    )
    # Get total count without pagination for response
    all_events = _service.list_events(
        status=status,
        feedback_type=feedback_type,
        source=source,
        min_urgency=min_urgency,
        offset=0,
        limit=10000,
    )
    return FeedbackListResponse(total=len(all_events), items=events)


@router.get("/stats", response_model=StatsResponse)
async def get_feedback_stats() -> StatsResponse:
    """Get feedback statistics including response time, auto-reply rate, and breakdowns.

    Returns aggregate metrics useful for monitoring SLA compliance
    and understanding feedback patterns.
    """
    stats = _service.get_statistics()
    return StatsResponse(**stats)


@router.get("/knowledge-base", response_model=list[KBEntry])
async def list_knowledge_base(
    category: str | None = Query(None, description="Filter by category"),
    product_id: str | None = Query(None, description="Filter by product ID"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[KBEntry]:
    """List knowledge base entries with optional category/product filtering."""
    return _service._knowledge_base.list_entries(
        category=category,
        product_id=product_id,
        offset=offset,
        limit=limit,
    )


@router.post("/knowledge-base", response_model=KBEntry, status_code=201)
async def add_knowledge_base_entry(request: KBEntryCreateRequest) -> KBEntry:
    """Add a new entry to the knowledge base.

    Creates a new FAQ pair that will be used for auto-matching
    customer questions to known answers.
    """
    entry = await _service._knowledge_base.add_entry(
        question=request.question,
        answer=request.answer,
        category=request.category,
        product_id=request.product_id,
    )
    logger.info("KB entry created: id=%s", entry.id)
    return entry


@router.get("/{event_id}", response_model=FeedbackEvent)
async def get_feedback_event(event_id: str) -> FeedbackEvent:
    """Get detailed information about a single feedback event.

    Returns the full event including classification results,
    auto-generated reply, and current status.
    """
    event = _service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Feedback event not found: {event_id}")
    return event


@router.post("/{event_id}/approve", response_model=FeedbackEvent)
async def approve_reply(event_id: str, request: ApproveRequest) -> FeedbackEvent:
    """Approve (or reject) an auto-generated reply for a feedback event.

    If approved, the reply is sent through the appropriate channel.
    An optional edited_reply can override the auto-generated content.

    If not approved, the event returns to draft status for manual handling.
    """
    event = _service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Feedback event not found: {event_id}")

    if event.status != FeedbackStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Event is not awaiting approval (current status: {event.status.value})",
        )

    if request.approve:
        reply_content = request.edited_reply or event.auto_reply
        if not reply_content:
            raise HTTPException(status_code=400, detail="No reply content available")

        success = await _service.submit_reply(
            event_id=event_id,
            reply_content=reply_content,
        )
        if not success:
            raise HTTPException(status_code=502, detail="Failed to send reply via channel API")
    else:
        # Rejected: move back to draft for manual reply
        event.status = FeedbackStatus.DRAFT_READY

    return _service.get_event(event_id) or event


@router.post("/{event_id}/reply", response_model=FeedbackEvent)
async def submit_manual_reply(event_id: str, request: ManualReplyRequest) -> FeedbackEvent:
    """Submit a manual reply for a feedback event.

    Used by human operators to provide custom responses that override
    or replace auto-generated replies.
    """
    event = _service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Feedback event not found: {event_id}")

    if event.status == FeedbackStatus.REPLIED:
        raise HTTPException(status_code=400, detail="Event has already been replied to")

    success = await _service.submit_reply(
        event_id=event_id,
        reply_content=request.content,
        channel=request.channel,
    )
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send reply via channel API")

    return _service.get_event(event_id) or event
