"""Customer Feedback Management module.

Monitors, classifies, and responds to customer feedback (product reviews,
IM messages, after-sale disputes) within the 5-minute SLA target.
"""

from app.modules.feedback.classifier import AIClassifier
from app.modules.feedback.knowledge_base import KnowledgeBaseManager
from app.modules.feedback.responder import ResponseGenerator
from app.modules.feedback.router import router as feedback_router
from app.modules.feedback.service import FeedbackService

__all__ = [
    "AIClassifier",
    "FeedbackService",
    "KnowledgeBaseManager",
    "ResponseGenerator",
    "feedback_router",
]
