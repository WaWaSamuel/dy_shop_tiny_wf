"""Product Discovery & Sourcing module.

Scans trending products daily, evaluates demand/competition,
identifies 1688 sourcing options, and presents ranked shortlists
with margin estimates.
"""

from .router import router
from .scoring import TrendScorer
from .service import DiscoveryService
from .suppliers import SupplierMatcher

__all__ = [
    "DiscoveryService",
    "SupplierMatcher",
    "TrendScorer",
    "router",
]
