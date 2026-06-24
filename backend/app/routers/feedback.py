"""Feedback management router placeholder."""

from fastapi import APIRouter

router = APIRouter()

_FEEDBACK_ITEMS = [
    {
        "id": "1",
        "order_id": "ORD-20240615-001",
        "customer_name": "Zhang Wei",
        "content": "The product color is different from what was shown in the pictures. I want a refund.",
        "type": "complaint",
        "source": "douyin",
        "status": "ai_drafted",
        "urgency": "high",
        "sentiment_score": -0.7,
        "ai_draft_reply": "Dear customer, we apologize for the color discrepancy and can offer a refund or replacement.",
        "created_at": "2024-06-15T10:30:00Z",
        "updated_at": "2024-06-15T10:31:00Z",
    },
    {
        "id": "2",
        "order_id": "ORD-20240615-002",
        "customer_name": "Li Na",
        "content": "When will my order be shipped? I ordered 3 days ago.",
        "type": "inquiry",
        "source": "im",
        "status": "pending",
        "urgency": "medium",
        "sentiment_score": -0.3,
        "ai_draft_reply": None,
        "created_at": "2024-06-15T11:15:00Z",
        "updated_at": "2024-06-15T11:15:00Z",
    },
    {
        "id": "3",
        "order_id": "ORD-20240614-018",
        "customer_name": "Wang Fang",
        "content": "Great quality! The dress fits perfectly. Will order again.",
        "type": "review",
        "source": "douyin",
        "status": "replied",
        "urgency": "low",
        "sentiment_score": 0.9,
        "ai_draft_reply": "Thank you so much for your kind words.",
        "created_at": "2024-06-14T16:00:00Z",
        "updated_at": "2024-06-14T16:05:00Z",
    },
]


@router.get("/")
async def list_feedback(
    status: str | None = None,
    type: str | None = None,
    source: str | None = None,
    urgency: str | None = None,
) -> dict[str, object]:
    """List customer feedback entries."""
    items = _FEEDBACK_ITEMS
    if status:
        items = [item for item in items if item["status"] == status]
    if type:
        items = [item for item in items if item["type"] == type]
    if source:
        items = [item for item in items if item["source"] == source]
    if urgency:
        items = [item for item in items if item["urgency"] == urgency]
    return {"items": items, "total": len(items)}


@router.get("/stats")
async def feedback_stats() -> dict[str, object]:
    """Return dashboard-friendly feedback stats."""
    return {
        "total_today": 42,
        "pending_responses": 7,
        "avg_response_time_min": 4.2,
        "auto_reply_rate": 0.78,
        "sentiment_breakdown": {"positive": 45, "neutral": 30, "negative": 25},
    }


@router.get("/{feedback_id}")
async def get_feedback(feedback_id: str) -> dict[str, object]:
    """Return a single feedback item."""
    for item in _FEEDBACK_ITEMS:
        if item["id"] == feedback_id:
            return item
    return {"id": feedback_id, "status": "not_found"}


@router.post("/{feedback_id}/approve")
async def approve_feedback(feedback_id: str) -> dict[str, str]:
    """Pretend to approve an AI draft."""
    return {"id": feedback_id, "status": "approved"}


@router.post("/{feedback_id}/reply")
async def reply_feedback(feedback_id: str) -> dict[str, str]:
    """Pretend to send a reply."""
    return {"id": feedback_id, "status": "replied"}
