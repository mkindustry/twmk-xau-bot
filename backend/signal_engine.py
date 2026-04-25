"""
TRADESWITHMK XAU INTEL BOT — Signal Engine
Computes confluence score and generates trade setups for XAU/USD.
All technical analysis is performed on data received from MT5 via the EA.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class MarketSnapshot:
    """Raw market data sent from MT5 EA every tick/bar."""
    symbol: str
    bid: float
    ask: float
    spread: float               # in points
    time: str                   # ISO UTC
    timeframe: str              # M1 | M5 | M15

    # Price data (OHLC last N candles)
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0

    # Technical indicators
    ema8: float = 0.0
    ema21: float = 0.0
    ema55: float = 0.0
    adx: float = 0.0
    atr: float = 0.0
    last_candle_body: float = 0.0
    last_candle_wick_high: float = 0.0
    last_candle_wick_low: float = 0.0
    tick_volume: int = 0

    # Session
    session: str = "UNKNOWN"    # ASIAN | LONDON | NY | OFF
    is_killzone: bool = False

    # Structure
    market_bias: str = "neutral"       # bullish | bearish | neutral
    has_bos: bool = False              # break of structure
    has_choch: bool = False            # change of character
    has_fvg: bool = False              # fair value gap
    fvg_high: float = 0.0
    fvg_low: float = 0.0
    has_order_block: bool = False
    ob_high: float = 0.0
    ob_low: float = 0.0
    has_liquidity_sweep: bool = False
    sweep_direction: str = ""          # HIGH | LOW
    is_premium: bool = False           # above 50% of range
    is_discount: bool = False          # below 50% of range

    # Asian range
    asian_high: float = 0.0
    asian_low: float = 0.0
    asian_range_set: bool = False

    # DXY (confirmation only)
    dxy_bias: str = "neutral"          # NEVER a primary trigger

    # Account info
    balance: float = 0.0
    equity: float = 0.0


@dataclass
class TradeSignal:
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    symbol: str = "XAUUSD"
    direction: str = ""         # BUY | SELL
    strategy: str = ""
    entry: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    confluence_score: int = 0
    score_breakdown: dict = field(default_factory=dict)
    session: str = ""
    generated_at: str = ""
    reasoning: str = ""
    is_executable: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Confluence Scoring ──────────────────────────────────────────────────────

class ConfluenceScorer:
    """
    Scores a trade setup from 0–100 using weighted components.
    Weights are configurable via config.yaml.
    """

    def __init__(self, weights: dict):
        self.w = weights

    def score(
        self,
        snap: MarketSnapshot,
        macro_score: int,
        news_bias: str,
        tweet_bias: str,
        direction: str,
    ) -> tuple[int, dict]:
        breakdown = {}

        # 1. Market Structure (20 pts)
        s = 0
        if snap.has_bos and snap.market_bias == direction.lower().replace("buy", "bullish").replace("sell", "bearish"):
            s += 15
        if snap.has_choch:
            s += 5
        breakdown["market_structure"] = min(s, self.w.get("market_structure", 20))

        # 2. EMA Alignment (15 pts)
        s = 0
        if direction == "BUY":
            if snap.ema8 > snap.ema21 > snap.ema55:
                s = 15
            elif snap.ema8 > snap.ema21:
                s = 8
        else:
            if snap.ema8 < snap.ema21 < snap.ema55:
                s = 15
            elif snap.ema8 < snap.ema21:
                s = 8
        breakdown["ema_alignment"] = min(s, self.w.get("ema_alignment", 15))

        # 3. ATR / Volatility (10 pts) — clean volatility, not excessive
        s = 0
        if snap.atr > 0:
            # Ideal: ATR in normal range, not spike territory
            spike_threshold = snap.atr * 2
            candle_ok = snap.last_candle_body < spike_threshold
            adx_ok = snap.adx >= 20
            if candle_ok and adx_ok:
                s = 10
            elif candle_ok or adx_ok:
                s = 5
        breakdown["atr_volatility"] = min(s, self.w.get("atr_volatility", 10))

        # 4. Session (10 pts)
        s = 0
        if snap.is_killzone:
            s = 10
        elif snap.session in ("LONDON", "NY"):
            s = 7
        elif snap.session == "OVERLAP":
            s = 10
        breakdown["valid_session"] = min(s, self.w.get("valid_session", 10))

        # 5. Liquidity Sweep (15 pts)
        s = 0
        if snap.has_liquidity_sweep:
            sweep_match = (
                (direction == "BUY" and snap.sweep_direction == "LOW") or
                (direction == "SELL" and snap.sweep_direction == "HIGH")
            )
            s = 15 if sweep_match else 5
        breakdown["liquidity_sweep"] = min(s, self.w.get("liquidity_sweep", 15))

        # 6. FVG / Order Block (15 pts)
        s = 0
        if snap.has_fvg:
            price = snap.bid
            in_fvg = snap.fvg_low <= price <= snap.fvg_high
            if in_fvg:
                s += 10
        if snap.has_order_block:
            price = snap.bid
            in_ob = snap.ob_low <= price <= snap.ob_high
            if in_ob:
                s += 5
        breakdown["fvg_order_block"] = min(s, self.w.get("fvg_order_block", 15))

        # 7. Macro/News Sentiment (15 pts)
        s = min(macro_score, self.w.get("macro_news_sentiment", 15))
        # Penalize if macro bias opposes trade direction
        if (direction == "BUY" and news_bias == "bearish") or \
           (direction == "SELL" and news_bias == "bullish"):
            s = max(0, s - 10)
        breakdown["macro_news_sentiment"] = s

        total = sum(breakdown.values())
        return min(total, 100), breakdown


# ── Strategy Detectors ──────────────────────────────────────────────────────

class StrategyDetector:
    """
    Detects which strategy (if any) is active given current market data.
    Returns (strategy_name, direction) or (None, None).
    """

    def __init__(self, config: dict):
        self.cfg = config
        self.tech = config.get("technical", {})
        self.ict = config.get("ict", {})
        self.strat = config.get("strategies", {})

    def detect(self, snap: MarketSnapshot) -> list[tuple[str, str]]:
        """Returns list of (strategy_name, direction) candidates."""
        candidates = []

        if self.strat.get("ema_stack_scalper"):
            r = self._ema_stack(snap)
            if r:
                candidates.append(r)

        if self.strat.get("spike_scalper"):
            r = self._spike_scalper(snap)
            if r:
                candidates.append(r)

        if self.strat.get("round_number_reactor"):
            r = self._round_number(snap)
            if r:
                candidates.append(r)

        if self.strat.get("london_liquidity_sweep"):
            r = self._london_sweep(snap)
            if r:
                candidates.append(r)

        if self.strat.get("asian_range_breakout") and snap.asian_range_set:
            r = self._asian_breakout(snap)
            if r:
                candidates.append(r)

        if self.strat.get("ict_logic"):
            r = self._ict_setup(snap)
            if r:
                candidates.append(r)

        return candidates

    def _ema_stack(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """EMA 8/21/55 stack with pullback entry."""
        if snap.adx < self.tech.get("adx_min", 20):
            return None
        price = snap.bid
        if snap.ema8 > snap.ema21 > snap.ema55:
            # Bullish stack — entry on pullback to EMA8/21
            if snap.ema21 <= price <= snap.ema8 * 1.002:
                if not snap.is_premium:  # don't buy too high
                    return ("EMA Stack Scalper", "BUY")
        elif snap.ema8 < snap.ema21 < snap.ema55:
            # Bearish stack — entry on pullback to EMA8/21
            if snap.ema21 >= price >= snap.ema8 * 0.998:
                if not snap.is_discount:  # don't sell too low
                    return ("EMA Stack Scalper", "SELL")
        return None

    def _spike_scalper(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """Detect explosive candles for momentum scalp."""
        if snap.atr <= 0:
            return None
        spike_mult = self.tech.get("atr_spike_multiplier", 2.0)
        is_spike = snap.last_candle_body > spike_mult * snap.atr
        if not is_spike:
            return None
        if snap.tick_volume < 100:
            return None
        # Entry in direction of spike if wick is minimal
        body_to_wick_ok = snap.last_candle_body > 0.6 * (
            snap.last_candle_body + snap.last_candle_wick_high + snap.last_candle_wick_low
        )
        if not body_to_wick_ok:
            return None
        if snap.close > snap.open:
            return ("Spike Scalper", "BUY")
        elif snap.close < snap.open:
            return ("Spike Scalper", "SELL")
        return None

    def _round_number(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """React to psychological XAU/USD levels."""
        zone = self.tech.get("round_number_zone_points", 150) * 0.01
        price = snap.bid
        # Round numbers: every $50 increment
        nearest_round = round(price / 50) * 50
        distance = abs(price - nearest_round)
        if distance > zone:
            return None
        # Need wick rejection + structure
        if snap.has_bos or snap.has_choch:
            # Bounce UP from round number support
            if price < nearest_round and snap.last_candle_wick_low > snap.atr * 0.5:
                return ("Round Number Reactor", "BUY")
            # Rejection DOWN from round number resistance
            if price > nearest_round and snap.last_candle_wick_high > snap.atr * 0.5:
                return ("Round Number Reactor", "SELL")
        return None

    def _london_sweep(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """Asian range sweep during London session."""
        if snap.session not in ("LONDON",):
            return None
        if not snap.asian_range_set:
            return None
        if not snap.has_liquidity_sweep:
            return None
        price = snap.bid
        asian_mid = (snap.asian_high + snap.asian_low) / 2
        # Swept HIGH and returned below → SELL
        if snap.sweep_direction == "HIGH" and price < snap.asian_high:
            if snap.has_bos or snap.has_choch:
                return ("London Liquidity Sweep", "SELL")
        # Swept LOW and returned above → BUY
        if snap.sweep_direction == "LOW" and price > snap.asian_low:
            if snap.has_bos or snap.has_choch:
                return ("London Liquidity Sweep", "BUY")
        return None

    def _asian_breakout(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """Asian range breakout continuation."""
        if not snap.asian_range_set:
            return None
        if snap.session not in ("LONDON", "NY"):
            return None
        price = snap.bid
        range_size = snap.asian_high - snap.asian_low
        if range_size < self.tech.get("asian_range_min_points", 100) * 0.01:
            return None
        # Confirmed breakout above Asian high
        if price > snap.asian_high + snap.atr * 0.3:
            if snap.ema8 > snap.ema21:   # trend confirmation
                return ("Asian Range Breakout", "BUY")
        # Confirmed breakdown below Asian low
        if price < snap.asian_low - snap.atr * 0.3:
            if snap.ema8 < snap.ema21:
                return ("Asian Range Breakout", "SELL")
        return None

    def _ict_setup(self, snap: MarketSnapshot) -> Optional[tuple[str, str]]:
        """ICT confluence: FVG + OB + sweep + structure."""
        ict_factors = 0
        direction = None

        if snap.has_liquidity_sweep:
            ict_factors += 1
            direction = "BUY" if snap.sweep_direction == "LOW" else "SELL"

        if snap.has_bos or snap.has_choch:
            ict_factors += 1

        if snap.has_fvg:
            ict_factors += 1

        if snap.has_order_block:
            ict_factors += 1

        # Premium/discount filter
        if direction == "BUY" and snap.is_discount:
            ict_factors += 1
        elif direction == "SELL" and snap.is_premium:
            ict_factors += 1

        min_factors = self.ict.get("min_confluence_factors", 2)
        if ict_factors >= min_factors and direction:
            return ("ICT Confluence", direction)
        return None


# ── Signal Engine ───────────────────────────────────────────────────────────

class SignalEngine:
    """
    Main orchestrator: receives market data, detects strategies,
    scores confluence, builds trade signals with full reasoning.
    """

    def __init__(self, config: dict, macro_analyzer=None, news_engine=None, twitter_engine=None):
        self.cfg = config
        self.macro = macro_analyzer
        self.news = news_engine
        self.twitter = twitter_engine

        weights = config.get("confluence", {}).get("weights", {})
        self.scorer = ConfluenceScorer(weights)
        self.detector = StrategyDetector(config)

        self.min_score = config.get("confluence", {}).get("min_score_to_trade", 75)
        self.alert_score = config.get("confluence", {}).get("min_score_alert_only", 60)
        self.priority_score = config.get("confluence", {}).get("min_score_priority", 85)

        self.latest_signal: Optional[TradeSignal] = None
        self.signal_history: list[TradeSignal] = []

    def process(self, snap: MarketSnapshot) -> Optional[TradeSignal]:
        """
        Main entry: given a market snapshot, return a TradeSignal or None.
        """
        # Get macro context
        macro_ctx = self.macro.analyze() if self.macro else None
        macro_score = macro_ctx.macro_score if macro_ctx else 0
        news_bias = macro_ctx.news_bias if macro_ctx else "neutral"
        tweet_bias = macro_ctx.tweet_bias if macro_ctx else "neutral"

        # Detect strategy candidates
        candidates = self.detector.detect(snap)
        if not candidates:
            return None

        # Score each candidate, pick the highest
        best_signal: Optional[TradeSignal] = None
        best_score = 0

        for strategy_name, direction in candidates:
            score, breakdown = self.scorer.score(
                snap, macro_score, news_bias, tweet_bias, direction
            )
            if score > best_score:
                best_score = score
                signal = self._build_signal(snap, strategy_name, direction, score, breakdown, macro_ctx)
                best_signal = signal

        if best_signal is None:
            return None

        self.latest_signal = best_signal
        self.signal_history.append(best_signal)
        if len(self.signal_history) > 200:
            self.signal_history = self.signal_history[-100:]

        return best_signal

    def _build_signal(
        self, snap, strategy, direction, score, breakdown, macro_ctx
    ) -> TradeSignal:
        entry = snap.ask if direction == "BUY" else snap.bid
        atr = snap.atr if snap.atr > 0 else 2.0

        # SL behind structure
        if direction == "BUY":
            sl = snap.ob_low if snap.has_order_block and snap.ob_low > 0 else entry - atr * 1.5
            tp1 = entry + atr * 1.5
            tp2 = entry + atr * 3.0
            tp3 = entry + atr * 5.0
        else:
            sl = snap.ob_high if snap.has_order_block and snap.ob_high > 0 else entry + atr * 1.5
            tp1 = entry - atr * 1.5
            tp2 = entry - atr * 3.0
            tp3 = entry - atr * 5.0

        # Round to 2 decimal places (XAU pricing)
        entry = round(entry, 2)
        sl = round(sl, 2)
        tp1 = round(tp1, 2)
        tp2 = round(tp2, 2)
        tp3 = round(tp3, 2)

        is_executable = score >= self.min_score
        reasoning = self._build_reasoning(
            snap, strategy, direction, entry, sl, tp1, tp2, tp3,
            score, breakdown, macro_ctx
        )

        signal = TradeSignal(
            symbol=snap.symbol,
            direction=direction,
            strategy=strategy,
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            confluence_score=score,
            score_breakdown=breakdown,
            session=snap.session,
            generated_at=datetime.now(timezone.utc).isoformat(),
            reasoning=reasoning,
            is_executable=is_executable,
            block_reason="" if is_executable else f"Score {score} < minimum {self.min_score}",
        )
        return signal

    def _build_reasoning(
        self, snap, strategy, direction, entry, sl, tp1, tp2, tp3,
        score, breakdown, macro_ctx
    ) -> str:
        rr = abs(tp2 - entry) / max(abs(sl - entry), 0.01)

        structure_desc = []
        if snap.has_bos:
            structure_desc.append("Break of Structure")
        if snap.has_choch:
            structure_desc.append("Change of Character")
        if snap.has_fvg:
            structure_desc.append(f"FVG [{snap.fvg_low:.2f}–{snap.fvg_high:.2f}]")
        if snap.has_order_block:
            structure_desc.append(f"Order Block [{snap.ob_low:.2f}–{snap.ob_high:.2f}]")
        if snap.has_liquidity_sweep:
            structure_desc.append(f"Liquidity Sweep ({snap.sweep_direction})")

        ema_desc = f"EMA8={snap.ema8:.2f} EMA21={snap.ema21:.2f} EMA55={snap.ema55:.2f}"
        if snap.ema8 > snap.ema21 > snap.ema55:
            ema_desc += " → Full bullish stack"
        elif snap.ema8 < snap.ema21 < snap.ema55:
            ema_desc += " → Full bearish stack"

        macro_desc = macro_ctx.reasoning if macro_ctx else "No macro data"

        # Why valid / why can fail
        valid_reasons = []
        fail_reasons = []

        if snap.is_killzone:
            valid_reasons.append("Active killzone session")
        if snap.has_liquidity_sweep:
            valid_reasons.append("Liquidity swept before entry")
        if score >= self.priority_score:
            valid_reasons.append(f"Priority score ({score}/100)")
        if snap.adx >= 25:
            valid_reasons.append(f"Strong trend (ADX {snap.adx:.1f})")

        if not snap.has_fvg and not snap.has_order_block:
            fail_reasons.append("No FVG or Order Block confirmed")
        if snap.adx < 20:
            fail_reasons.append(f"Weak trend (ADX {snap.adx:.1f})")
        if macro_ctx and macro_ctx.news_bias == ("bearish" if direction == "BUY" else "bullish"):
            fail_reasons.append("Macro bias opposes trade direction")
        if snap.spread > 25:
            fail_reasons.append(f"High spread ({snap.spread} pts)")

        lines = [
            f"▸ Market Bias: {snap.market_bias.upper()}",
            f"▸ Session: {snap.session}" + (" [KILLZONE]" if snap.is_killzone else ""),
            f"▸ Technical Setup: {strategy} | {ema_desc}",
            f"▸ Liquidity Context: {', '.join(structure_desc) or 'None'}",
            f"▸ Macro Context: {macro_desc}",
            f"▸ Tweet Context: {macro_ctx.tweet_bias if macro_ctx else 'neutral'}",
            f"▸ Confluence Score: {score}/100 {breakdown}",
            f"▸ Entry: {entry:.2f} ({direction})",
            f"▸ Stop Loss: {sl:.2f}",
            f"▸ Take Profit 1: {tp1:.2f}",
            f"▸ Take Profit 2: {tp2:.2f}",
            f"▸ Take Profit 3: {tp3:.2f}",
            f"▸ Risk/Reward (to TP2): {rr:.2f}R",
            f"▸ Invalidation: Close beyond SL {sl:.2f}",
            f"▸ Why valid: {' | '.join(valid_reasons) or 'Basic structure'}",
            f"▸ Why can fail: {' | '.join(fail_reasons) or 'Market reversal beyond SL'}",
        ]
        return "\n".join(lines)

    def get_latest_signal(self) -> Optional[dict]:
        if self.latest_signal:
            return self.latest_signal.to_dict()
        return None
