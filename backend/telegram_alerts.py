"""
TRADESWITHMK XAU INTEL BOT — Telegram Alerts
Clean, professional Telegram notifications for all bot events.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Alert type emoji map
EMOJIS = {
    "setup":        "🔍",
    "trade_open":   "✅",
    "tp1":          "🎯",
    "tp2":          "🎯🎯",
    "tp3":          "🏆",
    "be":           "🔒",
    "sl":           "❌",
    "news_block":   "📰",
    "risk_block":   "🛑",
    "macro":        "📊",
    "tweet":        "🐦",
    "kill_switch":  "⛔",
    "info":         "ℹ️",
    "error":        "🚨",
    "system":       "⚙️",
}


class TelegramAlerter:
    """
    Async Telegram message sender with retry logic and message formatting.
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._worker())
        logger.info("Telegram alerter started")

    async def stop(self):
        self._running = False

    async def _worker(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._send_raw(msg)
                self._queue.task_done()
                await asyncio.sleep(0.5)  # Telegram rate limit buffer
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Telegram worker error: {e}")

    async def _send_raw(self, text: str, retries: int = 3):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        return
                    logger.warning(f"Telegram HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"Telegram attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        logger.error("All Telegram retries failed")

    def _queue_message(self, text: str):
        try:
            self._queue.put_nowait(text)
        except asyncio.QueueFull:
            logger.warning("Telegram queue full — message dropped")

    # ── Formatted Alerts ────────────────────────────────────────

    def _header(self, alert_type: str, title: str) -> str:
        emoji = EMOJIS.get(alert_type, "ℹ️")
        ts = datetime.utcnow().strftime("%H:%M:%S UTC")
        return f"{emoji} <b>TRADESWITHMK XAU INTEL BOT</b>\n{emoji} <b>{title}</b>\n🕐 {ts}\n{'─' * 30}\n"

    def alert_setup_detected(
        self,
        symbol: str,
        direction: str,
        strategy: str,
        score: int,
        reasoning: str,
    ):
        msg = self._header("setup", "SETUP DETECTED — Not Executed")
        msg += (
            f"📌 <b>Symbol:</b> {symbol}\n"
            f"📌 <b>Direction:</b> {direction}\n"
            f"📌 <b>Strategy:</b> {strategy}\n"
            f"📊 <b>Score:</b> {score}/100\n"
            f"\n<b>Reasoning:</b>\n{reasoning}"
        )
        self._queue_message(msg)

    def alert_trade_open(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float,
        lot: float,
        risk_pct: float,
        score: int,
        strategy: str,
        reasoning: str,
    ):
        msg = self._header("trade_open", f"TRADE OPENED — {direction} {symbol}")
        msg += (
            f"🆔 <b>ID:</b> {trade_id}\n"
            f"📌 <b>Strategy:</b> {strategy}\n"
            f"💹 <b>Entry:</b> {entry:.3f}\n"
            f"🔴 <b>Stop Loss:</b> {sl:.3f}\n"
            f"🟢 <b>TP1:</b> {tp1:.3f}\n"
            f"🟢 <b>TP2:</b> {tp2:.3f}\n"
            f"🟢 <b>TP3:</b> {tp3:.3f}\n"
            f"📦 <b>Lot:</b> {lot}\n"
            f"⚠️ <b>Risk:</b> {risk_pct}%\n"
            f"📊 <b>Score:</b> {score}/100\n"
            f"\n<b>Reasoning:</b>\n{reasoning}"
        )
        self._queue_message(msg)

    def alert_tp_hit(self, trade_id: str, tp_level: int, price: float, pnl: float):
        alert_type = f"tp{tp_level}"
        msg = self._header(alert_type, f"TP{tp_level} HIT")
        msg += (
            f"🆔 <b>ID:</b> {trade_id}\n"
            f"💹 <b>Price:</b> {price:.3f}\n"
            f"💰 <b>P&L:</b> +${pnl:.2f}"
        )
        self._queue_message(msg)

    def alert_break_even(self, trade_id: str, price: float):
        msg = self._header("be", "BREAK-EVEN ACTIVATED")
        msg += (
            f"🆔 <b>ID:</b> {trade_id}\n"
            f"🔒 <b>SL moved to:</b> {price:.3f}\n"
            f"Risk is now <b>ZERO</b> on this trade."
        )
        self._queue_message(msg)

    def alert_sl_hit(self, trade_id: str, price: float, pnl: float):
        msg = self._header("sl", "STOP LOSS HIT")
        msg += (
            f"🆔 <b>ID:</b> {trade_id}\n"
            f"💹 <b>Price:</b> {price:.3f}\n"
            f"💸 <b>Loss:</b> -${abs(pnl):.2f}\n"
            f"📖 Review the trade journal."
        )
        self._queue_message(msg)

    def alert_news_block(self, event_name: str, minutes_to_event: int, direction: str = ""):
        msg = self._header("news_block", "TRADE BLOCKED — News")
        msg += (
            f"📰 <b>Event:</b> {event_name}\n"
            f"⏱️ <b>Time to event:</b> {minutes_to_event} min\n"
        )
        if direction:
            msg += f"❌ <b>Blocked direction:</b> {direction}\n"
        msg += "Trading paused during news blackout."
        self._queue_message(msg)

    def alert_risk_block(self, reason: str):
        msg = self._header("risk_block", "TRADE BLOCKED — Risk Limit")
        msg += f"🛑 <b>Reason:</b> {reason}"
        self._queue_message(msg)

    def alert_macro_event(
        self,
        event: str,
        actual: str,
        forecast: str,
        previous: str,
        impact: str,
        xau_bias: str,
    ):
        msg = self._header("macro", "MACRO EVENT ALERT")
        msg += (
            f"📰 <b>Event:</b> {event}\n"
            f"✅ <b>Actual:</b> {actual}\n"
            f"📋 <b>Forecast:</b> {forecast}\n"
            f"📋 <b>Previous:</b> {previous}\n"
            f"💥 <b>Impact:</b> {impact}\n"
            f"🥇 <b>XAU/USD Bias:</b> {xau_bias}"
        )
        self._queue_message(msg)

    def alert_tweet(
        self,
        account: str,
        tweet_text: str,
        categories: list[str],
        impact_score: int,
        xau_bias: str,
    ):
        if impact_score < 50:
            return
        msg = self._header("tweet", f"TWEET ALERT — @{account}")
        msg += (
            f"🐦 <b>Account:</b> @{account}\n"
            f"💬 <b>Tweet:</b> {tweet_text[:280]}\n"
            f"🏷️ <b>Categories:</b> {', '.join(categories)}\n"
            f"💥 <b>Impact:</b> {impact_score}/100\n"
            f"🥇 <b>XAU/USD Bias:</b> {xau_bias}"
        )
        self._queue_message(msg)

    def alert_kill_switch(self, reason: str = "Manual"):
        msg = self._header("kill_switch", "KILL SWITCH ACTIVATED")
        msg += (
            f"⛔ <b>Reason:</b> {reason}\n"
            f"All trading has been <b>HALTED</b>.\n"
            f"No new trades will be opened."
        )
        self._queue_message(msg)

    def alert_system(self, message: str):
        msg = self._header("system", "System Update")
        msg += message
        self._queue_message(msg)

    async def test_connection(self) -> bool:
        msg = (
            "🤖 <b>TRADESWITHMK XAU INTEL BOT</b>\n"
            "✅ Telegram connection successful!\n"
            f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        await self._send_raw(msg)
        return True
