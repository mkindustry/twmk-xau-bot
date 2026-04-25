# TRADESWITHMK XAU INTEL BOT

Professional algorithmic trading system for XAU/USD only.
Combines ICT methodology, macro analysis, news filtering, Twitter intelligence, and strict risk management.

---

## Architecture

```
mt5_ea/
  TradesWithMK_XAU_Bot.mq5    ← MT5 Expert Advisor (MQL5)

backend/
  main.py                     ← FastAPI app (all endpoints)
  signal_engine.py            ← Confluence scoring + strategy detection
  news_engine.py              ← Economic calendar (Finnhub, Trading Economics)
  twitter_engine.py           ← X/Twitter account monitoring
  macro_analyzer.py           ← Macro bias aggregator
  risk_manager.py             ← Position sizing + daily limits + journal
  telegram_alerts.py          ← Telegram notifications
  config.yaml                 ← All parameters
  .env.example                ← Environment variable template
  logs/                       ← Log files
  data/                       ← Trade journal (CSV) + signal history (JSON)
```

---

## Installation

### 1. Python Backend

**Requirements:** Python 3.11+

```bash
cd backend
pip install fastapi uvicorn httpx pyyaml python-dotenv tweepy
```

**Set up environment:**

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Start backend:**

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at `http://127.0.0.1:8000`
API docs at `http://127.0.0.1:8000/docs`

---

### 2. MT5 Expert Advisor

1. Copy `mt5_ea/TradesWithMK_XAU_Bot.mq5` to your MT5 `MQL5/Experts/` folder.
2. Open MetaEditor → Compile the file.
3. In MT5, go to **Tools → Options → Expert Advisors**:
   - ✅ Allow WebRequest for listed URL: `http://127.0.0.1:8000`
4. Attach the EA to a **XAU/USD M5** chart.
5. Set inputs:
   - `InpBackendURL = http://127.0.0.1:8000`
   - `InpApiToken` = value of `API_AUTH_TOKEN` in your `.env`
   - `InpBotMode` = `MODE_ALERT_ONLY` (start safe)
   - `InpPaperTrading = true` (paper trade first)

---

### 3. Telegram Bot Setup

1. Message `@BotFather` on Telegram → `/newbot` → get token.
2. Get your Chat ID: message `@userinfobot`.
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
4. Test: `POST http://127.0.0.1:8000/telegram/test`

---

### 4. News API Setup

**Finnhub (free tier available):**
- Register at https://finnhub.io
- Add `FINNHUB_KEY` to `.env`

**Trading Economics (paid):**
- Register at https://tradingeconomics.com/api
- Add `TRADING_ECONOMICS_KEY` to `.env`

---

### 5. Twitter/X API Setup

1. Apply at https://developer.twitter.com
2. Create a project and app
3. Get: API Key, API Secret, Bearer Token, Access Token, Access Token Secret
4. Add all 5 values to `.env`
5. Set `enabled: true` in `config.yaml` under `twitter:`

---

## Bot Modes

| Mode | Behavior |
|------|----------|
| `alert_only` | Sends Telegram alerts only — no trades |
| `semi_auto` | Sends alert and waits for manual approval (Telegram) |
| `full_auto` | Executes automatically if score ≥ `min_confluence_score` |

**Always start in `alert_only` mode. Monitor for at least 1 week before going semi_auto.**

---

## Confluence Score (0–100)

| Component | Max Points |
|-----------|-----------|
| Market Structure (BOS/CHoCH) | 20 |
| EMA 8/21/55 alignment | 15 |
| ATR / Volatility quality | 10 |
| Valid session / killzone | 10 |
| Liquidity sweep | 15 |
| FVG / Order Block | 15 |
| Macro/News sentiment | 15 |

| Score | Action |
|-------|--------|
| < 60 | No action |
| 60–74 | Alert only |
| 75–84 | Normal trade (if mode allows) |
| 85+ | Priority trade |

---

## Risk Rules (Non-Negotiable)

- No martingale, no grid, no position doubling after loss
- Max risk per trade: configurable (default 0.5%)
- Hard stop at daily loss limit
- Lock profits at daily profit target
- Break-even at 1R
- 50% partial close at TP1
- Trailing stop after TP1
- Cooldown period after consecutive losses
- No trade during news blackout window (20 min before/after high impact USD events)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System status |
| POST | `/signal/process` | Submit market snapshot from EA |
| GET | `/signal/latest` | Latest generated signal |
| GET | `/trade/reasoning` | Full trade reasoning text |
| POST | `/trade/open` | Register opened trade |
| POST | `/trade/close` | Register closed trade |
| POST | `/account/update` | Sync account balance/equity |
| GET | `/risk/status` | Daily risk stats |
| GET | `/news/latest` | Latest economic events |
| GET | `/tweets/latest` | Latest tweet signals |
| POST | `/telegram/test` | Send test Telegram message |
| POST | `/kill_switch?activate=true` | Emergency halt |
| GET | `/backtest/report` | Trade journal stats |
| GET | `/config/current` | View current config |
| POST | `/config/update` | Update config value |

---

## Trade Reasoning Example

```
▸ Market Bias: BULLISH
▸ Session: LONDON [KILLZONE]
▸ Technical Setup: London Liquidity Sweep | EMA8=4754.20 EMA21=4751.80 EMA55=4747.30 → Full bullish stack
▸ Liquidity Context: Liquidity Sweep (LOW), Break of Structure, FVG [4750.30–4752.10]
▸ Macro Context: News bias: bullish | Core PCE missed forecast → dovish signal
▸ Tweet Context: bullish
▸ Confluence Score: 82/100
▸ Entry: 4752.30 (BUY)
▸ Stop Loss: 4747.80
▸ Take Profit 1: 4757.00
▸ Take Profit 2: 4762.00
▸ Take Profit 3: 4770.00
▸ Risk/Reward (to TP2): 2.2R
▸ Invalidation: Close beyond SL 4747.80
▸ Why valid: Active killzone session | Liquidity swept before entry | Score 82/100
▸ Why can fail: No FVG confirmed on M1 | Macro could reverse on next data
```

---

## DXY Note

> DXY is a **confirmation filter only** — it is never a primary trade trigger.
> A trade cannot be opened solely based on DXY movement.

---

## Safety Checklist Before Going Live

- [ ] Paper traded for minimum 2 weeks
- [ ] Kill switch tested
- [ ] Telegram alerts working
- [ ] Spread filter confirmed
- [ ] Daily loss limit tested (simulate)
- [ ] Backend stays running (use PM2 or systemd or Task Scheduler)
- [ ] MT5 WebRequest URL whitelisted
- [ ] API auth token set in both `.env` and EA input
- [ ] Backtest reviewed at `/backtest/report`

---

## Disclaimer

This software is for educational and research purposes.
Trading XAU/USD carries significant financial risk.
Past performance does not guarantee future results.
Use at your own risk. The authors accept no liability for trading losses.
