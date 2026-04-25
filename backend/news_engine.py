"""
TRADESWITHMK XAU INTEL BOT — News Engine
Fetches, filters, and scores economic calendar events.
Determines XAU/USD macro bias from news surprises.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NewsEvent:
    id: str
    title: str
    country: str
    currency: str
    impact: str             # LOW | MEDIUM | HIGH
    event_time: datetime
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    surprise_direction: str = "neutral"   # positive | negative | neutral
    xau_bias: str = "neutral"             # bullish | bearish | neutral
    impact_score: int = 0
    source: str = ""


# ── XAU/USD Macro Bias Logic ────────────────────────────────────────────────

def _parse_number(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    clean = s.replace("%", "").replace("K", "000").replace("M", "000000").replace(",", "").strip()
    try:
        return float(clean)
    except (ValueError, TypeError):
        return None


def _determine_xau_bias(event: NewsEvent) -> tuple[str, int]:
    """
    Return (xau_bias, impact_score) based on event type and surprise magnitude.

    Rules (simplified macro logic):
    - Hawkish USD (strong CPI, NFP beat, rate hike)  → bearish gold
    - Dovish USD (miss on jobs, cut, soft CPI)        → bullish gold
    - Geopolitical/risk-off                           → bullish gold
    - Strong DXY drivers                              → bearish gold (confirmation only)
    """
    title_lower = event.title.lower()
    actual = _parse_number(event.actual)
    forecast = _parse_number(event.forecast)
    previous = _parse_number(event.previous)

    surprise = None
    if actual is not None and forecast is not None:
        surprise = actual - forecast

    # Determine surprise direction
    if surprise is not None:
        event.surprise_direction = "positive" if surprise > 0 else "negative" if surprise < 0 else "neutral"

    base_score = {"LOW": 20, "MEDIUM": 50, "HIGH": 80}.get(event.impact, 30)
    if surprise is not None:
        magnitude = min(abs(surprise) / max(abs(forecast or 1), 0.01), 1.0)
        base_score = min(100, int(base_score + magnitude * 20))

    # ── Inflation Events ────────────────────────────────────────
    if any(kw in title_lower for kw in ["cpi", "ppi", "core pce", "pce", "inflation"]):
        if event.surprise_direction == "positive":   # inflation hotter → hawkish
            return "bearish", min(base_score + 10, 100)
        elif event.surprise_direction == "negative": # inflation cooler → dovish
            return "bullish", min(base_score + 10, 100)

    # ── Employment Events ───────────────────────────────────────
    if any(kw in title_lower for kw in ["nfp", "non-farm", "employment", "payroll"]):
        if event.surprise_direction == "positive":
            return "bearish", base_score
        elif event.surprise_direction == "negative":
            return "bullish", base_score

    if any(kw in title_lower for kw in ["unemployment", "jobless", "initial claims"]):
        # Higher unemployment = more dovish → bullish gold
        if event.surprise_direction == "positive":
            return "bullish", base_score
        elif event.surprise_direction == "negative":
            return "bearish", base_score

    # ── Fed / Rate Decisions ────────────────────────────────────
    if any(kw in title_lower for kw in ["fomc", "fed", "interest rate", "powell", "rate decision"]):
        if "hike" in title_lower or "raise" in title_lower:
            return "bearish", min(base_score + 15, 100)
        if "cut" in title_lower or "lower" in title_lower:
            return "bullish", min(base_score + 15, 100)
        return "neutral", base_score

    # ── GDP ─────────────────────────────────────────────────────
    if "gdp" in title_lower:
        if event.surprise_direction == "positive":
            return "bearish", base_score     # strong economy → less safe haven
        elif event.surprise_direction == "negative":
            return "bullish", base_score

    # ── PMI / Business Activity ─────────────────────────────────
    if any(kw in title_lower for kw in ["pmi", "ism", "manufacturing", "services"]):
        if event.surprise_direction == "positive":
            return "bearish", base_score
        elif event.surprise_direction == "negative":
            return "bullish", base_score

    # ── Retail Sales ────────────────────────────────────────────
    if "retail" in title_lower:
        if event.surprise_direction == "positive":
            return "bearish", base_score
        elif event.surprise_direction == "negative":
            return "bullish", base_score

    # Default: no strong directional signal
    return "neutral", base_score


class NewsEngine:
    """
    Polls multiple news APIs and maintains a real-time event cache.
    """

    def __init__(self, config: dict, telegram=None):
        self.cfg = config
        self.news_cfg = config.get("news", {})
        self.apis = config.get("apis", {})
        self.telegram = telegram
        self.events: list[NewsEvent] = []
        self._lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        await self.fetch_all()
        self._poll_task = asyncio.create_task(self._polling_loop())
        logger.info("NewsEngine started")

    async def stop(self):
        if self._poll_task:
            self._poll_task.cancel()

    async def _polling_loop(self):
        while True:
            await asyncio.sleep(300)  # refresh every 5 min
            try:
                await self.fetch_all()
            except Exception as e:
                logger.error(f"NewsEngine poll error: {e}")

    async def fetch_all(self):
        tasks = []
        if self.apis.get("finnhub_key"):
            tasks.append(self._fetch_finnhub())
        if self.apis.get("trading_economics_key"):
            tasks.append(self._fetch_trading_economics())
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_events = []
        for r in results:
            if isinstance(r, list):
                all_events.extend(r)
            elif isinstance(r, Exception):
                logger.warning(f"News fetch error: {r}")

        # Deduplicate by title + time proximity
        seen = set()
        deduped = []
        for e in sorted(all_events, key=lambda x: x.event_time):
            key = f"{e.title[:30]}_{e.event_time.strftime('%Y%m%d%H')}"
            if key not in seen:
                seen.add(key)
                bias, score = _determine_xau_bias(e)
                e.xau_bias = bias
                e.impact_score = score
                deduped.append(e)

        async with self._lock:
            self.events = deduped
        logger.info(f"NewsEngine: loaded {len(deduped)} events")

    async def _fetch_finnhub(self) -> list[NewsEvent]:
        key = self.apis["finnhub_key"]
        now = datetime.now(timezone.utc)
        from_ts = int((now - timedelta(hours=2)).timestamp())
        to_ts = int((now + timedelta(hours=24)).timestamp())
        url = f"https://finnhub.io/api/v1/calendar/economic?from={now.date()}&to={(now + timedelta(days=1)).date()}&token={key}"
        events = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
                for item in data.get("economicCalendar", []):
                    currency = item.get("country", "")
                    impact_map = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}
                    impact = impact_map.get(item.get("impact", 1), "LOW")
                    currency_str = item.get("currency", "USD")
                    if currency_str not in self.news_cfg.get("currencies_to_watch", ["USD"]):
                        continue
                    try:
                        dt = datetime.fromisoformat(item.get("time", "").replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    events.append(NewsEvent(
                        id=f"finnhub_{item.get('id', '')}",
                        title=item.get("event", ""),
                        country=item.get("country", ""),
                        currency=currency_str,
                        impact=impact,
                        event_time=dt,
                        actual=str(item.get("actual")) if item.get("actual") else None,
                        forecast=str(item.get("estimate")) if item.get("estimate") else None,
                        previous=str(item.get("prev")) if item.get("prev") else None,
                        source="finnhub",
                    ))
        except Exception as e:
            logger.error(f"Finnhub fetch error: {e}")
        return events

    async def _fetch_trading_economics(self) -> list[NewsEvent]:
        key = self.apis["trading_economics_key"]
        now = datetime.now(timezone.utc)
        url = f"https://api.tradingeconomics.com/calendar/country/united states/{now.date()}/{(now + timedelta(days=1)).date()}?c={key}&f=json"
        events = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
                for item in data:
                    importance = item.get("Importance", 1)
                    impact_map = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}
                    impact = impact_map.get(importance, "LOW")
                    try:
                        dt_str = item.get("Date", "")
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    events.append(NewsEvent(
                        id=f"te_{item.get('CalendarId', '')}",
                        title=item.get("Event", ""),
                        country=item.get("Country", ""),
                        currency=item.get("Currency", "USD"),
                        impact=impact,
                        event_time=dt,
                        actual=str(item.get("Actual")) if item.get("Actual") else None,
                        forecast=str(item.get("Forecast")) if item.get("Forecast") else None,
                        previous=str(item.get("Previous")) if item.get("Previous") else None,
                        source="trading_economics",
                    ))
        except Exception as e:
            logger.error(f"TradingEconomics fetch error: {e}")
        return events

    # ── Queries ────────────────────────────────────────────────

    def is_blackout_window(self, symbol: str = "XAUUSD") -> tuple[bool, Optional[str], int]:
        """
        Returns (in_blackout, event_name, minutes_to_event).
        Checks blackout before AND after high-impact USD events.
        """
        now = datetime.now(timezone.utc)
        before_min = self.news_cfg.get("blackout_before_minutes", 20)
        after_min = self.news_cfg.get("blackout_after_minutes", 20)
        high_impact = self.news_cfg.get("high_impact_events", [])

        async with asyncio.Lock():
            pass  # just a pattern — not actually async here

        for event in self.events:
            if event.impact != "HIGH":
                continue
            title_match = any(kw.lower() in event.title.lower() for kw in high_impact)
            if not title_match:
                continue
            if event.currency not in ("USD", "XAU"):
                continue
            diff = (event.event_time - now).total_seconds() / 60
            if -after_min <= diff <= before_min:
                return True, event.title, int(diff)
        return False, None, 0

    def get_upcoming_events(self, hours: int = 4) -> list[dict]:
        now = datetime.now(timezone.utc)
        result = []
        for e in self.events:
            diff = (e.event_time - now).total_seconds() / 60
            if 0 <= diff <= hours * 60:
                result.append({
                    "title": e.title,
                    "time": e.event_time.isoformat(),
                    "impact": e.impact,
                    "currency": e.currency,
                    "actual": e.actual,
                    "forecast": e.forecast,
                    "previous": e.previous,
                    "xau_bias": e.xau_bias,
                    "impact_score": e.impact_score,
                    "minutes_away": round(diff, 1),
                })
        return sorted(result, key=lambda x: x["minutes_away"])

    def get_macro_bias(self) -> str:
        """
        Aggregate bias from recent high-impact events (last 2 hours).
        Returns: bullish | bearish | neutral
        """
        now = datetime.now(timezone.utc)
        recent = [
            e for e in self.events
            if e.impact == "HIGH"
            and abs((e.event_time - now).total_seconds()) <= 7200
            and e.xau_bias != "neutral"
        ]
        if not recent:
            return "neutral"
        bulls = sum(1 for e in recent if e.xau_bias == "bullish")
        bears = sum(1 for e in recent if e.xau_bias == "bearish")
        if bulls > bears:
            return "bullish"
        elif bears > bulls:
            return "bearish"
        return "neutral"

    def get_latest_events(self, limit: int = 10) -> list[dict]:
        return [
            {
                "title": e.title,
                "time": e.event_time.isoformat(),
                "impact": e.impact,
                "currency": e.currency,
                "actual": e.actual,
                "forecast": e.forecast,
                "previous": e.previous,
                "xau_bias": e.xau_bias,
                "impact_score": e.impact_score,
                "source": e.source,
            }
            for e in sorted(self.events, key=lambda x: x.event_time, reverse=True)[:limit]
        ]
