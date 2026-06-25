"""Same-source supplier matching on 1688 (image + keyword fusion).

Given a selected product (its main image + title/category), this finds the
best "same-source" (同源) 1688 supplier by running both the image search
(以图搜图) and the keyword search, then fusing the two result sets with a
combined score:

    fused_score = w_sim * similarity + w_quality * shop_quality

``similarity`` rewards items that appear in the image-search channel (and
rank highly there) plus lexical overlap with the title; ``shop_quality``
normalizes supplier rating and transaction volume. Items found by both
channels get a cross-channel agreement bonus, which is the strongest signal
that a 1688 offer is genuinely the same product.
"""

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter
from app.modules.discovery.suppliers import SupplierMatcher, SupplierResult

logger = logging.getLogger(__name__)

# Fusion weights.
_W_SIMILARITY = 0.65
_W_QUALITY = 0.35
# Cross-channel agreement bonus added to similarity when an offer shows up in
# both the image and keyword channels.
_AGREEMENT_BONUS = 0.20
# Normalization ceiling for transaction counts (anything >= caps at 1.0).
_TXN_CAP = 5000.0


@dataclass(slots=True)
class MatchedSupplier:
    """A fused 1688 match with its score components."""

    supplier: SupplierResult
    similarity: float
    quality: float
    fused_score: float
    in_image_channel: bool
    in_keyword_channel: bool


class SourceMatcher:
    """Finds the best same-source 1688 supplier for a selected product."""

    def __init__(self, rate_limiter: TokenBucketRateLimiter) -> None:
        self.rate_limiter = rate_limiter
        self.supplier_matcher = SupplierMatcher(rate_limiter)

    async def close(self) -> None:
        await self.supplier_matcher.close()

    async def find_best_match(
        self,
        title: str,
        image_url: str | None = None,
        min_rating: float = 4.5,
        min_transactions: int = 500,
        min_score: float | None = None,
    ) -> MatchedSupplier | None:
        """Find the single best same-source supplier, or None if none qualify.

        Args:
            title: Product title / keywords for the keyword channel.
            image_url: Main image URL for the image channel (optional).
            min_rating: Quality floor on supplier rating.
            min_transactions: Quality floor on historical transactions.
            min_score: Minimum fused score to accept (defaults to config).

        Returns:
            The top MatchedSupplier above the threshold, or None.
        """
        ranked = await self.rank_matches(
            title=title,
            image_url=image_url,
            min_rating=min_rating,
            min_transactions=min_transactions,
        )
        if not ranked:
            return None

        threshold = (
            min_score if min_score is not None else settings.FULFILLMENT_MIN_MATCH_SCORE
        )
        best = ranked[0]
        if best.fused_score < threshold:
            logger.info(
                "Best 1688 match for '%s' scored %.3f < threshold %.3f; rejecting",
                title[:40],
                best.fused_score,
                threshold,
            )
            return None
        return best

    async def rank_matches(
        self,
        title: str,
        image_url: str | None = None,
        min_rating: float = 4.5,
        min_transactions: int = 500,
    ) -> list[MatchedSupplier]:
        """Run both channels, fuse, and return matches sorted by fused score."""
        keyword = title[:30].strip()

        image_results: list[SupplierResult] = []
        if image_url:
            try:
                image_results = await self.supplier_matcher.search_by_image(image_url)
            except Exception as e:
                logger.warning("Image-channel search failed for '%s': %s", keyword, e)

        keyword_results: list[SupplierResult] = []
        try:
            keyword_results = await self.supplier_matcher.search_by_keyword(keyword)
        except Exception as e:
            logger.warning("Keyword-channel search failed for '%s': %s", keyword, e)

        fused = self._fuse(title, image_results, keyword_results)

        # Apply quality floors after fusion so a strong image match with a
        # slightly-low transaction count is not discarded prematurely.
        filtered = [
            m
            for m in fused
            if m.supplier.supplier_rating >= min_rating
            and m.supplier.transaction_count >= min_transactions
        ]
        filtered.sort(key=lambda m: m.fused_score, reverse=True)
        return filtered

    def _fuse(
        self,
        title: str,
        image_results: list[SupplierResult],
        keyword_results: list[SupplierResult],
    ) -> list[MatchedSupplier]:
        """Merge the two channels into scored, de-duplicated matches."""
        title_terms = self._tokenize(title)

        # Map supplier identity -> (result, image_rank, keyword_rank).
        merged: dict[str, dict] = {}

        for rank, res in enumerate(image_results):
            key = self._identity(res)
            merged.setdefault(key, {"res": res, "img_rank": None, "kw_rank": None})
            merged[key]["img_rank"] = rank

        for rank, res in enumerate(keyword_results):
            key = self._identity(res)
            entry = merged.setdefault(
                key, {"res": res, "img_rank": None, "kw_rank": None}
            )
            entry["kw_rank"] = rank
            # Prefer the richer record if the keyword one has more fields.
            if not entry["res"].image_url and res.image_url:
                entry["res"] = res

        n_img = max(len(image_results), 1)
        matches: list[MatchedSupplier] = []
        for entry in merged.values():
            res: SupplierResult = entry["res"]
            in_img = entry["img_rank"] is not None
            in_kw = entry["kw_rank"] is not None

            # Image-channel similarity: higher rank => higher score.
            img_sim = (1.0 - entry["img_rank"] / n_img) if in_img else 0.0
            # Lexical similarity from title overlap (keyword channel relevance).
            lex_sim = self._lexical_overlap(title_terms, res.product_title)

            similarity = max(img_sim, lex_sim)
            if in_img and in_kw:
                similarity = min(1.0, similarity + _AGREEMENT_BONUS)

            quality = self._quality(res)
            fused_score = _W_SIMILARITY * similarity + _W_QUALITY * quality

            matches.append(
                MatchedSupplier(
                    supplier=res,
                    similarity=round(similarity, 4),
                    quality=round(quality, 4),
                    fused_score=round(fused_score, 4),
                    in_image_channel=in_img,
                    in_keyword_channel=in_kw,
                )
            )

        return matches

    @staticmethod
    def _identity(res: SupplierResult) -> str:
        """Stable de-dup key for an offer across channels."""
        return res.product_url or f"{res.supplier_id}:{res.product_title}"

    @staticmethod
    def _quality(res: SupplierResult) -> float:
        """Normalize rating (0-5) and transaction count into a 0-1 quality."""
        rating_norm = min(max(res.supplier_rating / 5.0, 0.0), 1.0)
        txn_norm = min(res.transaction_count / _TXN_CAP, 1.0)
        return 0.6 * rating_norm + 0.4 * txn_norm

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Cheap bi-gram tokenizer that works for CJK and latin text."""
        cleaned = "".join(c if c.isalnum() else " " for c in text.lower())
        tokens: set[str] = set()
        for word in cleaned.split():
            if word.isascii():
                tokens.add(word)
            else:
                # CJK: character bi-grams capture product-name overlap well.
                if len(word) == 1:
                    tokens.add(word)
                for i in range(len(word) - 1):
                    tokens.add(word[i : i + 2])
        return tokens

    @classmethod
    def _lexical_overlap(cls, title_terms: set[str], candidate_title: str) -> float:
        """Jaccard-style overlap between title and candidate offer title."""
        if not title_terms:
            return 0.0
        cand_terms = cls._tokenize(candidate_title)
        if not cand_terms:
            return 0.0
        intersection = len(title_terms & cand_terms)
        union = len(title_terms | cand_terms)
        return intersection / union if union else 0.0
