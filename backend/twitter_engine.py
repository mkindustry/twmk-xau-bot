"""
TRADESWITHMK XAU INTEL BOT — Twitter/X Engine
Monitors key financial accounts and scores tweets for XAU/USD impact.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TweetSignal:
    tweet_id: str
    account: str
    text: str
    created_at: datetime
    categories: list[str] = field(default_factory=list)
    keywords_matched: list[str] = field(default_factory=list)
    impact_score: int = 0
    xau_bias: str = "neutral"      # bullish | bearish | neutral
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Keyword → Category Map ──────────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "fed": [
        "federal reserve", "fed", "fomc", "powell", "rate hike", "rate cut",
        "interest rate", "quantitative easing", "qe", "qt", "tapering", "pivot",
        "dovish", "hawkish", "balance sheet",
    ],
    "inflation": [
        "inflation", "cpi", "ppi", "pce", "core inflation", "deflation",
        "price pressure", "hot inflation", "cool inflation",
    ],
    "employment": [
        "nfp", "non-farm", "payrolls", "unemployment", "jobless claims",
        "hiring", "layoffs", "jobs report", "adp", "labor market",
    ],
    "macro": [
        "gdp", "recession", "growth", "economy", "economic", "pmi",
        "retail sales", "consumer confidence", "ism", "manufacturing",
    ],
    "geopolitical": [
        "war", "conflict", "military", "sanction", "nuclear", "attack",
        "crisis", "tension", "invasion", "strike", "terror",
    ],
    "dollar": [
        "dollar", "usd", "dxy", "greenback", "currency", "forex",
        "devaluation", "reserve currency",
    ],
    "yields": [
        "treasury", "yield", "10-year", "bond", "t-bill", "debt ceiling",
        "bund", "gilt", "fixed income",
    ],
    "china": [
        "china", "chinese", "prc", "pboc", "yuan", "renminbi",
        "beijing", "xi jinping", "taiwan", "hong kong",
    ],
    "middle_east": [
        "middle east", "israel", "iran", "saudi", "opec", "oil",
        "crude", "hamas", "hezbollah", "persian gulf",
    ],
    "gold": [
        "gold", "xau", "precious metal", "bullion", "safe haven",
        "store of value", "comex",
    ],
}

# ── Impact Rules for XAU/USD ────────────────────────────────────────────────

BULLISH_PHRASES = [
    "rate cut", "dovish", "pivot", "recession", "crisis", "emergency",
    "war", "conflict", "sanction", "nuclear", "collapse", "default",
    "safe haven", "gold buying", "lower rates", "soft landing failed",
    "inflation surge", "dollar weakness",
]

BEARISH_PHRASES = [
    "rate hike", "hawkish", "strong jobs", "hot inflation",
    "strong dollar", "risk on", "growth beats", "economy strong",
    "yield surge", "dollar strength", "aggressive fed",
]

NOISE_PHRASES = [
    "retweet", "follow me", "join my", "promo", "giveaway",
    "subscribe", "click here", "discount", "coupon",
]


class TwitterEngine:
    """
    Polls X/Twitter API v2 for recent tweets from configured accounts.
    Scores and classifies each tweet for XAU/USD impact.
    """

    def __init__(self, config: dict, telegram=None):
        self.cfg = config.get("twitter", {})
        self.telegram = telegram
        self.bearer_token = self.cfg.get("bearer_token", "")
        self.accounts: list[str] = self.cfg.get("accounts_to_watch", [])
        self.poll_interval: int = self.cfg.get("poll_interval_seconds", 60)
        self.min_alert_score: int = config.get("telegram", {}).get("min_tweet_impact_to_alert", 70)

        self.recent_signals: list[TweetSignal] = []
        self._seen_ids: set[str] = set()
        self._user_id_cache: dict[str, str] = {}  # username → user_id
        self._poll_task: Optional[asyncio.Task] = None
        self._latest_bias: str = "neutral"

    async def start(self):
        if not self.bearer_token or not self.cfg.get("enabled", False):
            logger.info("TwitterEngine disabled or no bearer token")
            return
        await self._resolve_user_ids()
        self._poll_task = asyncio.create_task(self._polling_loop())
        logger.info(f"TwitterEngine started — watching {len(self.accounts)} accounts")

    async def stop(self):
        if self._poll_task:
            self._poll_task.cancel()

    async def _polling_loop(self):
        while True:
            try:
                await self._fetch_recent_tweets()
            except Exception as e:
                logger.error(f"Twitter poll error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _resolve_user_ids(self):
        """Convert usernames to user IDs for the API."""
        if not self.accounts:
            return
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        usernames = ",".join(self.accounts[:100])  # API limit
        url = f"https://api.twitter.com/2/users/by?usernames={usernames}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()
                for user in data.get("data", []):
                    self._user_id_cache[user["username"].lower()] = user["id"]
            logger.info(f"Resolved {len(self._user_id_cache)} Twitter user IDs")
        except Exception as e:
            logger.error(f"Twitter user ID resolution failed: {e}")

    async def _fetch_recent_tweets(self):
        if not self._user_id_cache:
            await self._resolve_user_ids()
            if not self._user_id_cache:
                return

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        new_signals = []

        for username, user_id in self._user_id_cache.items():
            url = (
                f"https://api.twitter.com/2/users/{user_id}/tweets"
                f"?max_results=5&tweet.fields=created_at,text&exclude=retweets,replies"
            )
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 429:
                        logger.warning("Twitter rate limit hit — backing off")
                        await asyncio.sleep(60)
                        continue
                    data = resp.json()
                    for tweet in data.get("data", []):
                        tid = tweet["id"]
                        if tid in self._seen_ids:
                            continue
                        self._seen_ids.add(tid)
                        try:
                            created = datetime.fromisoformat(
                                tweet.get("created_at", "").replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            created = datetime.now(timezone.utc)
                        signal = self._analyze_tweet(tid, username, tweet["text"], created)
                        if signal.impact_score > 0:
                            new_signals.append(signal)
            except Exception as e:
                logger.debug(f"Tweet fetch error for @{username}: {e}")

        for signal in new_signals:
            self.recent_signals.append(signal)
            if len(self.recent_signals) > 500:
                self.recent_signals = self.recent_signals[-200:]

            if signal.impact_score >= self.min_alert_score and self.telegram:
                self.telegram.alert_tweet(
                    account=signal.account,
                    tweet_text=signal.text,
                    categories=signal.categories,
                    impact_score=signal.impact_score,
                    xau_bias=signal.xau_bias,
                )

        # Recalculate aggregate bias
        self._update_bias()

    def _analyze_tweet(
        self, tweet_id: str, account: str, text: str, created_at: datetime
    ) -> TweetSignal:
        text_lower = text.lower()

        # Filter noise
        is_noise = any(p in text_lower for p in NOISE_PHRASES)
        if is_noise:
            return TweetSignal(
                tweet_id=tweet_id, account=account, text=text,
                created_at=created_at, impact_score=0, xau_bias="neutral"
            )

        # Categorize
        categories = []
        matched_keywords = []
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    if cat not in categories:
                        categories.append(cat)
                    matched_keywords.append(kw)

        if not categories:
            return TweetSignal(
                tweet_id=tweet_id, account=account, text=text,
                created_at=created_at, impact_score=0, xau_bias="neutral"
            )

        # Base score from category weight
        category_weights = {
            "fed": 30, "inflation": 25, "geopolitical": 25,
            "gold": 20, "yields": 20, "employment": 20,
            "macro": 15, "dollar": 15, "china": 15,
            "middle_east": 15,
        }
        base_score = min(sum(category_weights.get(c, 10) for c in categories), 60)

        # High-impact account bonus
        high_impact_accounts = {"federalreserve", "potus", "realdonaldtrump", "whitehouse", "ustreasury"}
        if account.lower() in high_impact_accounts:
            base_score = min(base_score + 20, 100)

        # Sentiment adjustment
        bullish_hits = sum(1 for p in BULLISH_PHRASES if p in text_lower)
        bearish_hits = sum(1 for p in BEARISH_PHRASES if p in text_lower)

        score = min(base_score + bullish_hits * 5 + bearish_hits * 5, 100)

        if bullish_hits > bearish_hits:
            bias = "bullish"
        elif bearish_hits > bullish_hits:
            bias = "bearish"
        else:
            bias = "neutral"

        return TweetSignal(
            tweet_id=tweet_id,
            account=account,
            text=text,
            created_at=created_at,
            categories=categories,
            keywords_matched=list(set(matched_keywords)),
            impact_score=score,
            xau_bias=bias,
        )

    def _update_bias(self):
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        recent = [s for s in self.recent_signals if s.created_at >= cutoff and s.impact_score >= 40]
        if not recent:
            self._latest_bias = "neutral"
            return
        bulls = sum(s.impact_score for s in recent if s.xau_bias == "bullish")
        bears = sum(s.impact_score for s in recent if s.xau_bias == "bearish")
        if bulls > bears * 1.2:
            self._latest_bias = "bullish"
        elif bears > bulls * 1.2:
            self._latest_bias = "bearish"
        else:
            self._latest_bias = "neutral"

    # ── Public API ─────────────────────────────────────────────

    def get_current_bias(self) -> str:
        return self._latest_bias

    def get_latest_signals(self, limit: int = 10) -> list[dict]:
        return [
            {
                "account": s.account,
                "text": s.text[:280],
                "categories": s.categories,
                "impact_score": s.impact_score,
                "xau_bias": s.xau_bias,
                "created_at": s.created_at.isoformat(),
            }
            for s in sorted(self.recent_signals, key=lambda x: x.created_at, reverse=True)[:limit]
        ]

    def get_aggregate_impact_score(self) -> int:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = [s for s in self.recent_signals if s.created_at >= cutoff]
        if not recent:
            return 0
        return min(int(sum(s.impact_score for s in recent) / len(recent)), 100)
