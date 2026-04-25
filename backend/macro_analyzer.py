"""
TRADESWITHMK XAU INTEL BOT — Macro Analyzer
Aggregates macro context from news and tweets into a unified XAU/USD bias.
DXY is a confirmation filter — NEVER a primary trade trigger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class MacroContext:
    xau_bias: str           # bullish | bearish | neutral
    confidence: int         # 0–100
    news_bias: str
    tweet_bias: str
    macro_score: int        # component of confluence score (max 15 pts)
    reasoning: str
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()


BIAS_TO_SCORE = {"bullish": 1, "neutral": 0, "bearish": -1}


class MacroAnalyzer:
    """
    Combines NewsEngine and TwitterEngine signals into a single macro context.
    Used as one component of the overall confluence score.
    """

    def __init__(self, news_engine=None, twitter_engine=None, config: dict = None):
        self.news = news_engine
        self.twitter = twitter_engine
        self.cfg = config or {}

    def analyze(self) -> MacroContext:
        news_bias = self.news.get_macro_bias() if self.news else "neutral"
        tweet_bias = self.twitter.get_current_bias() if self.twitter else "neutral"
        tweet_score = self.twitter.get_aggregate_impact_score() if self.twitter else 0

        upcoming = self.news.get_upcoming_events(hours=1) if self.news else []
        has_imminent_high_impact = any(
            e["impact"] == "HIGH" and e["minutes_away"] <= 30
            for e in upcoming
        )

        # Aggregate
        votes = [BIAS_TO_SCORE[news_bias], BIAS_TO_SCORE[tweet_bias]]
        aggregate = sum(votes)

        if aggregate >= 1:
            final_bias = "bullish"
        elif aggregate <= -1:
            final_bias = "bearish"
        else:
            final_bias = "neutral"

        # If imminent high-impact news → lower confidence
        confidence = 70 if news_bias != "neutral" else 40
        if tweet_bias != "neutral":
            confidence = min(confidence + 15, 100)
        if tweet_score > 70:
            confidence = min(confidence + 10, 100)
        if has_imminent_high_impact:
            confidence = max(confidence - 30, 10)
            final_bias = "neutral"

        # Macro score contribution to confluence (max 15 pts)
        if final_bias != "neutral" and confidence >= 60:
            macro_score = 15 if confidence >= 80 else 10
        elif final_bias != "neutral":
            macro_score = 7
        else:
            macro_score = 0

        # Build reasoning string
        parts = []
        if news_bias != "neutral":
            parts.append(f"News bias: {news_bias}")
        if tweet_bias != "neutral":
            parts.append(f"Social/tweet bias: {tweet_bias} (score {tweet_score}/100)")
        if has_imminent_high_impact:
            events_str = ", ".join(e["title"] for e in upcoming if e["impact"] == "HIGH")
            parts.append(f"CAUTION — high-impact event imminent: {events_str}")
        if not parts:
            parts.append("No significant macro driver detected")

        reasoning = " | ".join(parts)

        return MacroContext(
            xau_bias=final_bias,
            confidence=confidence,
            news_bias=news_bias,
            tweet_bias=tweet_bias,
            macro_score=macro_score,
            reasoning=reasoning,
        )

    def format_for_reasoning(self, context: MacroContext) -> str:
        return (
            f"Macro XAU Bias: {context.xau_bias.upper()} "
            f"(confidence {context.confidence}%) | "
            f"{context.reasoning}"
        )
