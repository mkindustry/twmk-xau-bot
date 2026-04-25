"""
TRADESWITHMK XAU INTEL BOT — Risk Manager
Strict institutional-grade risk management for XAU/USD.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    id: str
    symbol: str
    direction: str          # BUY | SELL
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_amount: float
    risk_pct: float
    confluence_score: int
    strategy: str
    session: str
    open_time: str
    close_time: str = ""
    close_price: float = 0.0
    pnl: float = 0.0
    status: str = "OPEN"    # OPEN | TP1 | TP2 | TP3 | SL | BE | MANUAL
    reasoning: str = ""


@dataclass
class DailyStats:
    date: str = ""
    trades_opened: int = 0
    trades_closed: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    consecutive_losses: int = 0
    max_drawdown_pct: float = 0.0
    blocked_by_daily_loss: bool = False
    blocked_by_daily_profit: bool = False


class RiskManager:
    """
    Enforces all risk rules before any trade is allowed.
    Single source of truth for position sizing and daily limits.
    """

    def __init__(self, config: dict, journal_path: str = "data/trade_journal.csv"):
        self.cfg = config["risk"]
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        self.daily: DailyStats = DailyStats(date=str(date.today()))
        self.open_trades: dict[str, TradeRecord] = {}
        self.account_balance: float = 10_000.0   # updated by EA ping
        self.account_equity: float = 10_000.0
        self.peak_equity: float = 10_000.0

        self._init_journal()
        self._load_today()

    # ── Journal ────────────────────────────────────────────────

    def _init_journal(self):
        if not self.journal_path.exists():
            headers = list(TradeRecord.__dataclass_fields__.keys())
            with open(self.journal_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=headers).writeheader()

    def _load_today(self):
        """Reconstruct today's stats from journal."""
        today = str(date.today())
        self.daily = DailyStats(date=today)
        if not self.journal_path.exists():
            return
        with open(self.journal_path, "r") as f:
            for row in csv.DictReader(f):
                if row.get("open_time", "")[:10] == today:
                    self.daily.trades_opened += 1
                    status = row.get("status", "")
                    pnl = float(row.get("pnl", 0))
                    if status not in ("OPEN",):
                        self.daily.trades_closed += 1
                        self.daily.pnl += pnl
                        if pnl > 0:
                            self.daily.wins += 1
                            self.daily.consecutive_losses = 0
                        else:
                            self.daily.losses += 1
                            self.daily.consecutive_losses += 1

    def _append_journal(self, trade: TradeRecord):
        headers = list(TradeRecord.__dataclass_fields__.keys())
        row = asdict(trade)
        with open(self.journal_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(row)

    def _update_journal_row(self, trade: TradeRecord):
        rows = []
        headers = list(TradeRecord.__dataclass_fields__.keys())
        with open(self.journal_path, "r") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["id"] == trade.id:
                row.update(asdict(trade))
        with open(self.journal_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    # ── Account Update ─────────────────────────────────────────

    def update_account(self, balance: float, equity: float):
        self.account_balance = balance
        self.account_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
        dd = (self.peak_equity - equity) / self.peak_equity * 100
        self.daily.max_drawdown_pct = max(self.daily.max_drawdown_pct, dd)
        self.daily.pnl_pct = (equity - self.account_balance) / self.account_balance * 100

    # ── Pre-Trade Validation ────────────────────────────────────

    def can_trade(self) -> tuple[bool, str]:
        """
        Returns (allowed, reason). Must return True before opening any trade.
        """
        cfg = self.cfg

        # Daily loss limit
        loss_pct = abs(min(self.daily.pnl, 0)) / self.account_balance * 100
        if loss_pct >= cfg["max_daily_loss"]:
            self.daily.blocked_by_daily_loss = True
            return False, f"Daily loss limit reached ({loss_pct:.2f}% >= {cfg['max_daily_loss']}%)"

        # Daily profit target
        profit_pct = max(self.daily.pnl, 0) / self.account_balance * 100
        if profit_pct >= cfg["max_daily_profit"]:
            self.daily.blocked_by_daily_profit = True
            return False, f"Daily profit target reached ({profit_pct:.2f}% >= {cfg['max_daily_profit']}%)"

        # Max trades per day
        if self.daily.trades_opened >= cfg["max_trades_per_day"]:
            return False, f"Max trades/day reached ({self.daily.trades_opened})"

        # Max consecutive losses
        if self.daily.consecutive_losses >= cfg["max_consecutive_losses"]:
            return False, f"Consecutive losses: {self.daily.consecutive_losses} — cooldown required"

        # Kill switch
        return True, "OK"

    def check_spread(self, spread_points: float) -> tuple[bool, str]:
        max_sp = self.cfg.get("max_spread_points", 35)
        if spread_points > max_sp:
            return False, f"Spread too wide: {spread_points} pts > {max_sp} pts"
        return True, "OK"

    # ── Position Sizing ─────────────────────────────────────────

    def calculate_lot_size(
        self,
        entry: float,
        sl: float,
        risk_pct: Optional[float] = None,
    ) -> tuple[float, float]:
        """
        Returns (lot_size, risk_amount_usd).
        Uses 1 lot = 100 oz = $100 per pip ($10 per 0.10 pip).
        Point value for XAUUSD: 1 point = $0.01 × 100 oz = $1.00 per 0.01 lot.
        """
        rp = risk_pct or self.cfg["risk_per_trade"]
        risk_amount = self.account_balance * rp / 100
        sl_distance = abs(entry - sl)

        if sl_distance <= 0:
            logger.error("SL distance is 0 — cannot size position")
            return 0.01, 0.0

        # XAUUSD: 1 standard lot = 100 oz
        # Pip value ≈ $1 per 0.01 lot per 1-point move
        # lot_size = risk_amount / (sl_distance_in_points * pip_value_per_lot)
        # pip_value_per_lot for XAUUSD standard lot ≈ $1 per point
        # sl_distance in price (e.g. 2.50) → points = 250
        sl_points = sl_distance * 100  # 1 point = 0.01 price
        pip_value_per_lot = 1.0        # $1 per point per 1 std lot XAUUSD

        lot_size = risk_amount / (sl_points * pip_value_per_lot)
        lot_size = max(0.01, round(lot_size, 2))
        # Cap at 10 lots
        lot_size = min(lot_size, 10.0)

        actual_risk = sl_points * pip_value_per_lot * lot_size
        return lot_size, round(actual_risk, 2)

    # ── Trade Lifecycle ─────────────────────────────────────────

    def register_trade(self, trade: TradeRecord):
        if self.daily.date != str(date.today()):
            self.daily = DailyStats(date=str(date.today()))
        self.open_trades[trade.id] = trade
        self.daily.trades_opened += 1
        self._append_journal(trade)
        logger.info(f"Trade registered: {trade.id} {trade.direction} {trade.lot_size} lot @ {trade.entry}")

    def close_trade(self, trade_id: str, close_price: float, pnl: float, status: str):
        if trade_id not in self.open_trades:
            logger.warning(f"Trade {trade_id} not found in open trades")
            return
        trade = self.open_trades.pop(trade_id)
        trade.close_price = close_price
        trade.pnl = round(pnl, 2)
        trade.status = status
        trade.close_time = datetime.utcnow().isoformat()

        self.daily.trades_closed += 1
        self.daily.pnl += pnl
        if pnl > 0:
            self.daily.wins += 1
            self.daily.consecutive_losses = 0
        else:
            self.daily.losses += 1
            self.daily.consecutive_losses += 1

        self._update_journal_row(trade)
        logger.info(f"Trade closed: {trade_id} PnL={pnl:.2f} Status={status}")

    # ── Status ─────────────────────────────────────────────────

    def get_status(self) -> dict:
        allowed, reason = self.can_trade()
        return {
            "date": self.daily.date,
            "can_trade": allowed,
            "block_reason": reason if not allowed else None,
            "trades_opened": self.daily.trades_opened,
            "trades_closed": self.daily.trades_closed,
            "wins": self.daily.wins,
            "losses": self.daily.losses,
            "consecutive_losses": self.daily.consecutive_losses,
            "pnl_usd": round(self.daily.pnl, 2),
            "pnl_pct": round(self.daily.pnl_pct, 3),
            "max_drawdown_pct": round(self.daily.max_drawdown_pct, 3),
            "account_balance": self.account_balance,
            "account_equity": self.account_equity,
            "open_trades": len(self.open_trades),
            "blocked_by_daily_loss": self.daily.blocked_by_daily_loss,
            "blocked_by_daily_profit": self.daily.blocked_by_daily_profit,
        }
