"""Trend scoring engine for product discovery.

Applies weighted multi-factor scoring to rank candidate products
based on demand signals and competitive landscape.
"""

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.models.discovery import TrendingProduct


# Seasonal category mappings: month ranges of peak demand per category keyword.
SEASONAL_PEAKS: dict[str, list[tuple[int, int]]] = {
    "防晒": [(4, 8)],
    "保暖": [(10, 2)],
    "冬装": [(10, 1)],
    "夏装": [(4, 8)],
    "泳衣": [(5, 9)],
    "羽绒服": [(10, 2)],
    "圣诞": [(11, 12)],
    "春节": [(1, 2)],
    "开学": [(8, 9)],
    "618": [(5, 6)],
    "双11": [(10, 11)],
    "年货": [(1, 2)],
    "雨伞": [(4, 9)],
    "暖宝宝": [(10, 3)],
    "风扇": [(5, 9)],
    "取暖器": [(10, 3)],
}


@dataclass(slots=True)
class ScoringWeights:
    """Configurable weights for score calculation. Must sum to 1.0."""

    sales_growth_7d: float = 0.30
    search_volume_trend: float = 0.20
    competition_density_inv: float = 0.25
    competitor_review_quality_inv: float = 0.10
    seasonality_fit: float = 0.15

    def __post_init__(self) -> None:
        total = (
            self.sales_growth_7d
            + self.search_volume_trend
            + self.competition_density_inv
            + self.competitor_review_quality_inv
            + self.seasonality_fit
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")


@dataclass
class PercentileData:
    """Percentile distribution data for normalization."""

    p10: float = 0.0
    p25: float = 0.0
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0


class TrendScorer:
    """Calculates composite scores for trending product candidates.

    Uses a weighted multi-factor model:
        - Sales growth 7d: 30%
        - Search volume trend: 20%
        - Competition density (inverse): 25%
        - Competitor review quality (inverse): 10%
        - Seasonality fit: 15%
    """

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()

    def calculate_score(self, product: TrendingProduct) -> float:
        """Calculate weighted composite score for a product.

        Args:
            product: A TrendingProduct ORM instance with populated fields.

        Returns:
            Score between 0 and 100 representing product opportunity quality.
        """
        # Build percentile data from the product's own metrics as fallback.
        # In production, percentile_data would be computed across the full batch.
        growth_score = self._score_growth(product.growth_rate_7d)
        search_score = self._score_search_volume(product.search_volume)
        competition_score = self._score_competition_inverse(product.competition_count)
        review_score = self._score_review_quality_inverse(product.avg_competitor_rating)
        seasonality_score = self.check_seasonality(product.category, date.today())

        composite = (
            self.weights.sales_growth_7d * growth_score
            + self.weights.search_volume_trend * search_score
            + self.weights.competition_density_inv * competition_score
            + self.weights.competitor_review_quality_inv * review_score
            + self.weights.seasonality_fit * seasonality_score
        )

        return round(min(100.0, max(0.0, composite)), 2)

    def calculate_score_batch(
        self,
        products: list[TrendingProduct],
    ) -> list[tuple[TrendingProduct, float]]:
        """Score a batch of products using percentile normalization across the batch.

        Returns list of (product, score) tuples sorted descending by score.
        """
        if not products:
            return []

        # Compute percentile distributions from the batch
        growth_values = sorted(p.growth_rate_7d for p in products)
        search_values = sorted(p.search_volume for p in products)
        competition_values = sorted(p.competition_count for p in products)
        rating_values = sorted(p.avg_competitor_rating for p in products)

        growth_pdata = self._build_percentile_data(growth_values)
        search_pdata = self._build_percentile_data(search_values)
        competition_pdata = self._build_percentile_data(competition_values)
        rating_pdata = self._build_percentile_data(rating_values)

        results: list[tuple[TrendingProduct, float]] = []

        for product in products:
            growth_score = self.normalize_metric(product.growth_rate_7d, growth_pdata)
            search_score = self.normalize_metric(product.search_volume, search_pdata)
            # Inverse: lower competition is better
            competition_score = 100.0 - self.normalize_metric(
                product.competition_count, competition_pdata
            )
            # Inverse: lower average competitor rating = easier to compete
            review_score = 100.0 - self.normalize_metric(
                product.avg_competitor_rating, rating_pdata
            )
            seasonality_score = self.check_seasonality(product.category, date.today())

            composite = (
                self.weights.sales_growth_7d * growth_score
                + self.weights.search_volume_trend * search_score
                + self.weights.competition_density_inv * competition_score
                + self.weights.competitor_review_quality_inv * review_score
                + self.weights.seasonality_fit * seasonality_score
            )

            score = round(min(100.0, max(0.0, composite)), 2)
            results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @staticmethod
    def normalize_metric(value: float, percentile_data: PercentileData) -> float:
        """Normalize a metric value to 0-100 scale using percentile distribution.

        Maps value linearly between min and max of the observed distribution.
        Clips at 0 and 100.

        Args:
            value: The raw metric value.
            percentile_data: Distribution stats for normalization.

        Returns:
            Normalized value between 0.0 and 100.0.
        """
        range_val = percentile_data.max_val - percentile_data.min_val
        if range_val == 0:
            return 50.0  # All values identical

        normalized = ((value - percentile_data.min_val) / range_val) * 100.0
        return min(100.0, max(0.0, normalized))

    @staticmethod
    def check_seasonality(category: str, current_date: date) -> float:
        """Calculate seasonal trend score for a product category.

        Checks if the category matches seasonal peaks based on
        the current month. Returns a score 0-100 where 100 means
        the product is perfectly aligned with current seasonal demand.

        Args:
            category: Product category string (may contain seasonal keywords).
            current_date: The date to evaluate against.

        Returns:
            Seasonality fit score between 0.0 and 100.0.
        """
        current_month = current_date.month
        best_score = 50.0  # Neutral default for non-seasonal products

        for keyword, peak_ranges in SEASONAL_PEAKS.items():
            if keyword in category:
                for start_month, end_month in peak_ranges:
                    if _month_in_range(current_month, start_month, end_month):
                        # In peak season: high score
                        best_score = max(best_score, 90.0)
                    elif _months_until_range(current_month, start_month) <= 2:
                        # Approaching peak: good score (buying lead time)
                        best_score = max(best_score, 75.0)
                    elif _months_until_range(current_month, start_month) <= 4:
                        # Moderately ahead of season
                        best_score = max(best_score, 60.0)
                    else:
                        # Off-season
                        best_score = max(best_score, 20.0)

        return best_score

    def _score_growth(self, growth_rate: float) -> float:
        """Score growth rate using sigmoid-like mapping."""
        # Growth rate is a percentage; 50%+ is exceptional, 10% is moderate.
        if growth_rate <= 0:
            return 0.0
        # Use log scaling to handle wide range
        score = min(100.0, 20.0 * math.log1p(growth_rate))
        return score

    def _score_search_volume(self, volume: int) -> float:
        """Score search volume using log scaling."""
        if volume <= 0:
            return 0.0
        # Log scaling: 1000 -> ~69, 10000 -> ~92, 100000 -> 100
        score = min(100.0, 10.0 * math.log10(max(1, volume)))
        return score

    def _score_competition_inverse(self, competition_count: int) -> float:
        """Score competition inversely: fewer competitors = higher score."""
        if competition_count <= 0:
            return 100.0
        # 10 competitors -> ~77, 50 -> ~43, 200 -> ~13
        score = max(0.0, 100.0 - 25.0 * math.log1p(competition_count))
        return score

    def _score_review_quality_inverse(self, avg_rating: float) -> float:
        """Score competitor review quality inversely: lower ratings = easier market."""
        # Rating is 0-5; lower average ratings mean easier competition.
        if avg_rating <= 0:
            return 100.0
        # 5.0 -> 0, 4.0 -> 40, 3.0 -> 80
        score = max(0.0, (5.0 - avg_rating) * 40.0)
        return min(100.0, score)

    @staticmethod
    def _build_percentile_data(sorted_values: list[float]) -> PercentileData:
        """Build percentile data from a sorted list of values."""
        n = len(sorted_values)
        if n == 0:
            return PercentileData()

        def _percentile(pct: float) -> float:
            idx = int(pct / 100.0 * (n - 1))
            return sorted_values[min(idx, n - 1)]

        return PercentileData(
            p10=_percentile(10),
            p25=_percentile(25),
            p50=_percentile(50),
            p75=_percentile(75),
            p90=_percentile(90),
            min_val=sorted_values[0],
            max_val=sorted_values[-1],
        )


def _month_in_range(month: int, start: int, end: int) -> bool:
    """Check if month is within a start-end range (handles year wrap)."""
    if start <= end:
        return start <= month <= end
    else:
        # Wraps around December, e.g. Oct(10) to Feb(2)
        return month >= start or month <= end


def _months_until_range(current_month: int, start_month: int) -> int:
    """Calculate months until start of a seasonal range."""
    if current_month <= start_month:
        return start_month - current_month
    else:
        return 12 - current_month + start_month
