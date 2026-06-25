"""Pricing engine for sourced listings.

Computes a 抖店 sell price that hits a target gross margin given the full
1688 landed cost. Because the 抖店 platform commission is charged as a
percentage of the *sell price*, margin and price are interdependent; this
solves for price in closed form and then verifies/repairs the result
against the canonical landed-cost breakdown so the achieved margin never
falls below the configured floor.

Margin definition (gross margin on revenue):
    margin = (sell_price - landed_cost) / sell_price

With landed_cost = fixed_cost + commission_rate * sell_price, where
fixed_cost = wholesale + shipping + packaging, the target price is:
    sell_price = fixed_cost / (1 - commission_rate - target_margin)
"""

import logging
import math
from dataclasses import dataclass

from app.core.config import settings
from app.modules.discovery.suppliers import LandedCostBreakdown, SupplierMatcher

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PriceQuote:
    """A computed sell price with its margin breakdown."""

    sell_price: float
    target_margin: float
    achieved_margin: float
    landed_cost: float
    floor_price: float
    breakdown: LandedCostBreakdown
    feasible: bool
    reason: str = ""


class PricingEngine:
    """Solves for a sell price meeting a target gross-margin floor."""

    def __init__(
        self,
        target_margin: float | None = None,
        min_margin: float | None = None,
    ) -> None:
        self.target_margin = (
            target_margin if target_margin is not None else settings.FULFILLMENT_TARGET_MARGIN
        )
        self.min_margin = (
            min_margin if min_margin is not None else settings.FULFILLMENT_MIN_MARGIN
        )

    def quote(
        self,
        wholesale_price: float,
        delivery_loc: str,
        category: str,
    ) -> PriceQuote:
        """Compute a sell price targeting ``target_margin`` for the given cost.

        Args:
            wholesale_price: Per-unit 1688 cost.
            delivery_loc: Supplier origin (drives domestic shipping estimate).
            category: Product category (drives commission + packaging lookup).

        Returns:
            PriceQuote. ``feasible`` is False when the commission rate alone
            makes the target margin mathematically unreachable.
        """
        # Probe the cost structure with a unit sell price so we can read the
        # category commission rate and the fixed (price-independent) costs.
        probe = SupplierMatcher.calculate_landed_cost(
            wholesale_price=wholesale_price,
            delivery_loc=delivery_loc,
            category=category,
            sell_price=1.0,
        )
        commission_rate = probe.commission_rate
        fixed_cost = probe.wholesale_price + probe.shipping_cost + probe.packaging_cost

        denom = 1.0 - commission_rate - self.target_margin
        if denom <= 0:
            reason = (
                f"target margin {self.target_margin:.0%} unreachable: commission "
                f"{commission_rate:.0%} leaves no headroom"
            )
            logger.warning("Pricing infeasible: %s", reason)
            infeasible = SupplierMatcher.calculate_landed_cost(
                wholesale_price=wholesale_price,
                delivery_loc=delivery_loc,
                category=category,
                sell_price=0.0,
            )
            return PriceQuote(
                sell_price=0.0,
                target_margin=self.target_margin,
                achieved_margin=0.0,
                landed_cost=infeasible.total_landed_cost,
                floor_price=0.0,
                breakdown=infeasible,
                feasible=False,
                reason=reason,
            )

        raw_price = fixed_cost / denom
        # Round up to the nearest cent so rounding never erodes the margin.
        sell_price = math.ceil(raw_price * 100.0) / 100.0

        breakdown = self._verify(sell_price, wholesale_price, delivery_loc, category)

        # The floor price is the lowest sell price still meeting min_margin.
        floor_denom = 1.0 - commission_rate - self.min_margin
        floor_price = (
            math.ceil((fixed_cost / floor_denom) * 100.0) / 100.0
            if floor_denom > 0
            else sell_price
        )

        # Repair: if cent-rounding pushed achieved margin under the floor, bump.
        achieved = breakdown.margin_percentage / 100.0
        while achieved < self.min_margin:
            sell_price = round(sell_price + 0.01, 2)
            breakdown = self._verify(sell_price, wholesale_price, delivery_loc, category)
            achieved = breakdown.margin_percentage / 100.0

        return PriceQuote(
            sell_price=sell_price,
            target_margin=self.target_margin,
            achieved_margin=round(achieved, 4),
            landed_cost=breakdown.total_landed_cost,
            floor_price=floor_price,
            breakdown=breakdown,
            feasible=True,
        )

    @staticmethod
    def _verify(
        sell_price: float,
        wholesale_price: float,
        delivery_loc: str,
        category: str,
    ) -> LandedCostBreakdown:
        """Recompute the landed-cost breakdown at a concrete sell price."""
        return SupplierMatcher.calculate_landed_cost(
            wholesale_price=wholesale_price,
            delivery_loc=delivery_loc,
            category=category,
            sell_price=sell_price,
        )
