"""
TRADESWITHMK XAU INTEL BOT — FastAPI Backend
Main application entry point. Provides all REST endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Internal modules
from news_engine import NewsEngine
from twitter_engine import TwitterEngine
from macro_analyzer import MacroAnalyzer
from signal_engine import SignalEngine, MarketSnapshot
from risk_manager import RiskManager, TradeRecord
from telegram_alerts import TelegramAlerter

# ── Bootstrap ───────────────────────────────────────────────────────────────

load_dotenv()

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    # Expand environment variables
    _expand_env(raw)
    return raw


def _expand_env(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = _expand_env(v)
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var = obj[2:-1]
        return os.environ.get(var, "")
    return obj


# ── Global State ─────────────────────────────────────────────────────────────

config: dict = {}
news_engine: Optional[NewsEngine] = None
twitter_engine: Optional[TwitterEngine] = None
macro_analyzer: Optional[MacroAnalyzer] = None
signal_engine: Optional[SignalEngine] = None
risk_manager: Optional[RiskManager] = None
telegram: Optional[TelegramAlerter] = None
kill_switch_active: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, news_engine, twitter_engine, macro_analyzer
    global signal_engine, risk_manager, telegram, kill_switch_active

    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Config load failed: {e}")
        config = {}
    kill_switch_active = config.get("bot", {}).get("kill_switch", False)

    # Telegram — fire and forget, never block startup
    tg_cfg = config.get("telegram", {})
    telegram = TelegramAlerter(
        bot_token=tg_cfg.get("bot_token", ""),
        chat_id=tg_cfg.get("chat_id", ""),
    )
    await telegram.start()

    # News Engine — start background polling, don't await initial fetch
    news_engine = NewsEngine(config, telegram)
    asyncio.create_task(news_engine.start())

    # Twitter Engine — start background polling
    twitter_engine = TwitterEngine(config, telegram)
    asyncio.create_task(twitter_engine.start())

    # Macro Analyzer
    macro_analyzer = MacroAnalyzer(news_engine, twitter_engine, config)

    # Signal Engine
    signal_engine = SignalEngine(config, macro_analyzer, news_engine, twitter_engine)

    # Risk Manager
    try:
        risk_manager = RiskManager(config, config.get("backend", {}).get("trade_journal", "data/trade_journal.csv"))
    except Exception as e:
        logger.error(f"RiskManager init failed: {e}")

    asyncio.create_task(
        telegram.alert_system(
            f"Bot started ✅\nMode: {config.get('bot', {}).get('mode', 'alert_only')}\n"
            f"Paper Trading: {config.get('bot', {}).get('paper_trading', True)}"
        )
    )
    logger.info("TRADESWITHMK XAU INTEL BOT started")

    yield

    await telegram.stop()
    if news_engine:
        await news_engine.stop()
    if twitter_engine:
        await twitter_engine.stop()
    logger.info("Bot stopped")


app = FastAPI(
    title="TRADESWITHMK XAU INTEL BOT",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ─────────────────────────────────────────────────────────────────────

def verify_token(x_api_token: str = Header(...)):
    expected = os.environ.get("API_AUTH_TOKEN", "")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Request / Response Models ─────────────────────────────────────────────────

class MarketSnapshotRequest(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread: float
    time: str
    timeframe: str
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0
    ema8: float = 0.0
    ema21: float = 0.0
    ema55: float = 0.0
    adx: float = 0.0
    atr: float = 0.0
    last_candle_body: float = 0.0
    last_candle_wick_high: float = 0.0
    last_candle_wick_low: float = 0.0
    tick_volume: int = 0
    session: str = "UNKNOWN"
    is_killzone: bool = False
    market_bias: str = "neutral"
    has_bos: bool = False
    has_choch: bool = False
    has_fvg: bool = False
    fvg_high: float = 0.0
    fvg_low: float = 0.0
    has_order_block: bool = False
    ob_high: float = 0.0
    ob_low: float = 0.0
    has_liquidity_sweep: bool = False
    sweep_direction: str = ""
    is_premium: bool = False
    is_discount: bool = False
    asian_high: float = 0.0
    asian_low: float = 0.0
    asian_range_set: bool = False
    dxy_bias: str = "neutral"
    balance: float = 0.0
    equity: float = 0.0


class TradeOpenRequest(BaseModel):
    trade_id: str
    signal_id: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_pct: float
    confluence_score: int
    strategy: str
    session: str
    reasoning: str


class TradeCloseRequest(BaseModel):
    trade_id: str
    close_price: float
    pnl: float
    status: str     # TP1 | TP2 | TP3 | SL | BE | MANUAL


class AccountUpdateRequest(BaseModel):
    balance: float
    equity: float


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


class SemiAutoApprovalRequest(BaseModel):
    signal_id: str
    approved: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot": config.get("bot", {}).get("name"),
        "mode": config.get("bot", {}).get("mode"),
        "paper_trading": config.get("bot", {}).get("paper_trading"),
        "kill_switch": kill_switch_active,
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/signal/process")
async def process_signal(
    body: MarketSnapshotRequest,
    background_tasks: BackgroundTasks,
    x_api_token: str = Header(default=""),
):
    """
    Called by the MT5 EA on each bar/tick.
    Returns trade signal if conditions are met.
    """
    if kill_switch_active:
        return {"action": "HALT", "reason": "Kill switch active"}

    snap = MarketSnapshot(**body.dict())

    # Update account info
    if risk_manager and snap.balance > 0:
        risk_manager.update_account(snap.balance, snap.equity)

    # News blackout check
    in_blackout, event_name, mins = news_engine.is_blackout_window() if news_engine else (False, None, 0)
    if in_blackout:
        background_tasks.add_task(
            telegram.alert_news_block, event_name, abs(mins)
        )
        return {"action": "BLOCKED", "reason": f"News blackout: {event_name} in {mins} min"}

    # Risk check
    can_trade, block_reason = risk_manager.can_trade() if risk_manager else (True, "")
    if not can_trade:
        background_tasks.add_task(telegram.alert_risk_block, block_reason)
        return {"action": "BLOCKED", "reason": block_reason}

    # Spread check
    spread_ok, spread_reason = risk_manager.check_spread(snap.spread) if risk_manager else (True, "")
    if not spread_ok:
        return {"action": "BLOCKED", "reason": spread_reason}

    # Generate signal
    signal = signal_engine.process(snap) if signal_engine else None
    if signal is None:
        return {"action": "NO_SIGNAL"}

    mode = config.get("bot", {}).get("mode", "alert_only")

    if signal.confluence_score < config.get("confluence", {}).get("min_score_alert_only", 60):
        return {"action": "NO_SIGNAL", "score": signal.confluence_score}

    # Alert only mode
    if not signal.is_executable or mode == "alert_only":
        background_tasks.add_task(
            telegram.alert_setup_detected,
            signal.symbol, signal.direction, signal.strategy,
            signal.confluence_score, signal.reasoning
        )
        return {"action": "ALERT", "signal": signal.to_dict()}

    # Semi-auto: alert and wait for approval
    if mode == "semi_auto":
        background_tasks.add_task(
            telegram.alert_setup_detected,
            signal.symbol, signal.direction, signal.strategy,
            signal.confluence_score, signal.reasoning
        )
        return {"action": "AWAIT_APPROVAL", "signal": signal.to_dict()}

    # Full auto
    if mode == "full_auto" and signal.is_executable:
        lot, risk_amount = risk_manager.calculate_lot_size(signal.entry, signal.sl)
        return {
            "action": "EXECUTE",
            "signal": signal.to_dict(),
            "lot_size": lot,
            "risk_amount": risk_amount,
        }

    return {"action": "ALERT", "signal": signal.to_dict()}


@app.get("/signal/latest")
async def get_latest_signal():
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    sig = signal_engine.get_latest_signal()
    if not sig:
        return {"signal": None, "message": "No signal generated yet"}
    return {"signal": sig}


@app.get("/trade/reasoning")
async def get_reasoning():
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    sig = signal_engine.get_latest_signal()
    if not sig:
        return {"reasoning": "No signal available"}
    return {
        "signal_id": sig.get("signal_id"),
        "direction": sig.get("direction"),
        "strategy": sig.get("strategy"),
        "confluence_score": sig.get("confluence_score"),
        "reasoning": sig.get("reasoning"),
        "generated_at": sig.get("generated_at"),
    }


@app.post("/trade/open")
async def trade_opened(body: TradeOpenRequest, background_tasks: BackgroundTasks):
    """Called by EA when a trade is successfully opened."""
    trade = TradeRecord(
        id=body.trade_id,
        symbol="XAUUSD",
        direction=body.direction,
        entry=body.entry,
        sl=body.sl,
        tp1=body.tp1,
        tp2=body.tp2,
        tp3=body.tp3,
        lot_size=body.lot_size,
        risk_amount=0.0,
        risk_pct=body.risk_pct,
        confluence_score=body.confluence_score,
        strategy=body.strategy,
        session=body.session,
        open_time=datetime.now(timezone.utc).isoformat(),
        reasoning=body.reasoning,
    )
    if risk_manager:
        risk_manager.register_trade(trade)

    background_tasks.add_task(
        telegram.alert_trade_open,
        body.trade_id, "XAUUSD", body.direction,
        body.entry, body.sl, body.tp1, body.tp2, body.tp3,
        body.lot_size, body.risk_pct, body.confluence_score,
        body.strategy, body.reasoning
    )
    return {"status": "registered"}


@app.post("/trade/close")
async def trade_closed(body: TradeCloseRequest, background_tasks: BackgroundTasks):
    """Called by EA when a trade is closed."""
    if risk_manager:
        risk_manager.close_trade(body.trade_id, body.close_price, body.pnl, body.status)

    if body.status == "SL":
        background_tasks.add_task(
            telegram.alert_sl_hit, body.trade_id, body.close_price, body.pnl
        )
    elif body.status.startswith("TP"):
        tp_level = int(body.status[-1]) if body.status[-1].isdigit() else 1
        background_tasks.add_task(
            telegram.alert_tp_hit, body.trade_id, tp_level, body.close_price, body.pnl
        )
    elif body.status == "BE":
        background_tasks.add_task(
            telegram.alert_break_even, body.trade_id, body.close_price
        )
    return {"status": "closed"}


@app.post("/account/update")
async def update_account(body: AccountUpdateRequest):
    if risk_manager:
        risk_manager.update_account(body.balance, body.equity)
    return {"status": "updated"}


@app.get("/risk/status")
async def risk_status():
    if not risk_manager:
        raise HTTPException(503, "Risk manager not ready")
    return risk_manager.get_status()


@app.get("/news/latest")
async def news_latest():
    if not news_engine:
        raise HTTPException(503, "News engine not ready")
    return {
        "events": news_engine.get_latest_events(20),
        "upcoming": news_engine.get_upcoming_events(hours=4),
        "macro_bias": news_engine.get_macro_bias(),
        "blackout": news_engine.is_blackout_window()[0],
    }


@app.get("/tweets/latest")
async def tweets_latest():
    if not twitter_engine:
        raise HTTPException(503, "Twitter engine not ready")
    return {
        "signals": twitter_engine.get_latest_signals(15),
        "current_bias": twitter_engine.get_current_bias(),
        "aggregate_impact": twitter_engine.get_aggregate_impact_score(),
    }


@app.post("/telegram/test")
async def telegram_test():
    if not telegram:
        raise HTTPException(503, "Telegram not ready")
    result = await telegram.test_connection()
    return {"sent": result}


@app.post("/kill_switch")
async def toggle_kill_switch(activate: bool, background_tasks: BackgroundTasks):
    global kill_switch_active
    kill_switch_active = activate
    config["bot"]["kill_switch"] = activate
    if activate:
        background_tasks.add_task(telegram.alert_kill_switch, "API request")
    else:
        background_tasks.add_task(telegram.alert_system, "Kill switch DEACTIVATED — trading resumed")
    return {"kill_switch": kill_switch_active}


@app.get("/config/current")
async def get_config():
    safe_config = {k: v for k, v in config.items() if k not in ("apis",)}
    return safe_config


@app.post("/config/update")
async def update_config(body: ConfigUpdateRequest):
    keys = body.key.split(".")
    obj = config
    for k in keys[:-1]:
        if k not in obj:
            raise HTTPException(400, f"Key {k} not found")
        obj = obj[k]
    obj[keys[-1]] = body.value
    return {"updated": body.key, "value": body.value}


@app.get("/backtest/report")
async def backtest_report():
    journal_path = Path(config["backend"]["trade_journal"])
    if not journal_path.exists():
        return {"message": "No trade journal found"}
    import csv
    trades = []
    with open(journal_path) as f:
        trades = list(csv.DictReader(f))
    if not trades:
        return {"total_trades": 0}

    closed = [t for t in trades if t.get("status") != "OPEN"]
    wins = [t for t in closed if float(t.get("pnl", 0)) > 0]
    losses = [t for t in closed if float(t.get("pnl", 0)) <= 0]
    total_pnl = sum(float(t.get("pnl", 0)) for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0

    return {
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl_usd": round(total_pnl, 2),
        "avg_win": round(sum(float(t["pnl"]) for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(float(t["pnl"]) for t in losses) / len(losses), 2) if losses else 0,
        "trades": trades[-50:],  # last 50
    }


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    cfg = load_config().get("backend", {})
    uvicorn.run(
        "main:app",
        host=cfg.get("host", "0.0.0.0"),
        port=cfg.get("port", 8000),
        reload=False,
        log_level=cfg.get("log_level", "info").lower(),
    )
