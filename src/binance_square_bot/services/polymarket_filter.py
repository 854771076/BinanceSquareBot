"""
@file polymarket_filter.py
@description Filters and scores Polymarket markets to find the most interesting one to feature
@created-by fullstack-dev-workflow
"""

import logging

from binance_square_bot.config import config
from binance_square_bot.models.polymarket_market import PolymarketMarket

from loguru import logger


class PolymarketFilter:
    """Filters and scores Polymarket markets to find the most interesting one."""

    def __init__(
        self,
        min_volume: float | None = None,
        published_ids: set[str] | None = None,
    ):
        self.min_volume = min_volume if min_volume is not None else config.min_volume_threshold
        self.published_ids = published_ids or set()

    def filter_min_volume(self, markets: list[PolymarketMarket]) -> list[PolymarketMarket]:
        """Filter out markets with volume below minimum threshold."""
        return [m for m in markets if (m.volume or 0.0) >= self.min_volume]

    def exclude_published(self, markets: list[PolymarketMarket]) -> list[PolymarketMarket]:
        """Exclude already published markets."""
        return [m for m in markets if m.condition_id not in self.published_ids]

    def filter_win_rate_range(self, markets: list[PolymarketMarket], min_pct: float = 60.0, max_pct: float = 90.0) -> list[PolymarketMarket]:
        """Filter markets where either outcome (YES or NO) has win rate between min_pct and max_pct (percentages)."""
        filtered = []
        for market in markets:
            yes_pct = market.yes_price * 100
            no_pct = market.no_price * 100
            # Check if either outcome is in the desired range
            if (min_pct < yes_pct < max_pct) or (min_pct < no_pct < max_pct):
                filtered.append(market)
        return filtered

    def select_best_markets(self, markets: list[PolymarketMarket], limit: int = 3) -> list[PolymarketMarket]:
        """Select the top N best markets to feature based on scoring.
        Returns empty list if no markets meet criteria.
        """
        # Filter step 1: min volume
        candidates = self.filter_min_volume(markets)
        # Filter step 2: exclude published
        candidates = self.exclude_published(candidates)
        # Filter step 3: win rate range - either outcome between 60% and 90%
        candidates = self.filter_win_rate_range(candidates)

        if not candidates:
            logger.info("No candidate markets remaining after filtering")
            return []

        # Sort by score descending
        candidates.sort(key=lambda m: m.score(), reverse=True)

        # Take top N
        top_candidates = candidates[:limit]

        # Log top candidates
        logger.info(f"Selected top {len(top_candidates)} candidate markets:")
        for i, candidate in enumerate(top_candidates, 1):
            logger.info(
                "  %d: question='%s' condition_id=%s score=%.2f volume=%.0f yes_price=%.1f%%",
                i, candidate.question, candidate.condition_id, candidate.score(), candidate.volume, candidate.yes_price * 100
            )

        return top_candidates
