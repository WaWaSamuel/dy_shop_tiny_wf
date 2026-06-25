"""Fulfillment module: selection -> 1688 sourcing/listing -> order -> logistics.

Flow 1 (source -> list): match a selected product to a same-source 1688
supply (image + keyword fusion), price it for the target gross margin, and
list it on 抖店 with its ad assets.

Flow 2 (order -> fulfillment): ingest 抖店 orders (webhook primary, poll
fallback), place the matching 1688 order, track logistics, and push the
shipment back to 抖店.
"""

from .alibaba_order import AlibabaOrderClient
from .matcher import SourceMatcher
from .pricing import PricingEngine
from .router import router
from .service import FulfillmentService, SourceListingInput

__all__ = [
    "AlibabaOrderClient",
    "FulfillmentService",
    "PricingEngine",
    "SourceListingInput",
    "SourceMatcher",
    "router",
]
