import { useState, useCallback, useEffect } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

// ── Reusable form atoms ──────────────────────────────────────────

function Section({ title, icon, children }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-800 bg-gray-800/40">
        <span className="text-base">{icon}</span>
        <h3 className="text-white font-semibold text-sm">{title}</h3>
      </div>
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="space-y-1">
      <label className="text-gray-400 text-xs uppercase tracking-wider block">{label}</label>
      {children}
      {hint && <p className="text-gray-600 text-xs">{hint}</p>}
    </div>
  );
}

function Input({ value, onChange, type = "text", placeholder, secret }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={secret && !show ? "password" : type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-yellow-500/60 transition-colors placeholder-gray-600"
      />
      {secret && (
        <button onClick={() => setShow(s => !s)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-xs">
          {show ? "hide" : "show"}
        </button>
      )}
    </div>
  );
}

function NumberInput({ value, onChange, min, max, step = 0.1 }) {
  return (
    <input
      type="number" value={value} min={min} max={max} step={step}
      onChange={e => onChange(e.target.value)}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-yellow-500/60 transition-colors"
    />
  );
}

function Toggle({ value, onChange, label }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all w-full ${
        value
          ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400"
          : "bg-gray-800/60 border-gray-700 text-gray-500"
      }`}
    >
      <div className={`w-8 h-4 rounded-full relative transition-colors ${value ? "bg-yellow-500" : "bg-gray-600"}`}>
        <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${value ? "translate-x-4" : "translate-x-0.5"}`} />
      </div>
      {label}
    </button>
  );
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-yellow-500/60 transition-colors">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

// ── Twitter account manager ───────────────────────────────────

function TwitterAccounts({ accounts, onChange }) {
  const [newAcc, setNewAcc] = useState("");
  const add = () => {
    const clean = newAcc.replace("@", "").trim();
    if (clean && !accounts.includes(clean)) {
      onChange([...accounts, clean]);
      setNewAcc("");
    }
  };
  return (
    <div className="md:col-span-2 space-y-3">
      <label className="text-gray-400 text-xs uppercase tracking-wider block">Watched Twitter Accounts</label>
      <div className="flex flex-wrap gap-2">
        {accounts.map(a => (
          <span key={a} className="flex items-center gap-1 bg-gray-800 border border-gray-700 rounded-full px-3 py-1 text-sm text-gray-300">
            @{a}
            <button onClick={() => onChange(accounts.filter(x => x !== a))}
              className="text-gray-600 hover:text-red-400 ml-1 leading-none">×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={newAcc} onChange={e => setNewAcc(e.target.value)}
          onKeyDown={e => e.key === "Enter" && add()}
          placeholder="@handle or handle"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-yellow-500/60 placeholder-gray-600" />
        <button onClick={add}
          className="px-4 py-2 bg-yellow-500/20 border border-yellow-500/30 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors">
          Add
        </button>
      </div>
    </div>
  );
}

// ── Main Settings component ──────────────────────────────────

export function SettingsTab() {
  const { data: cfg } = usePolling(useCallback(() => api.config(), []), 60000);

  const [saved,   setSaved]   = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState(null);

  // Local form state — mirrors config.yaml sections
  const [bot,     setBot]     = useState({ mode: "alert_only", paper_trading: true, kill_switch: false });
  const [risk,    setRisk]    = useState({ risk_per_trade: 0.5, max_daily_loss: 2, max_daily_profit: 4, max_trades_per_day: 6, max_consecutive_losses: 3, cooldown_after_loss_minutes: 30, max_spread_points: 35, max_slippage_points: 20, break_even_at_r: 1.0, trailing_stop_after_tp1: true });
  const [conf,    setConf]    = useState({ min_score_to_trade: 75, min_score_alert_only: 60, min_score_priority: 85 });
  const [tech,    setTech]    = useState({ ema_fast: 8, ema_mid: 21, ema_slow: 55, adx_min: 20, atr_period: 14, atr_spike_multiplier: 2.0 });
  const [news,    setNews]    = useState({ enabled: true, blackout_before_minutes: 20, blackout_after_minutes: 20, reaction_mode_enabled: false });
  const [strat,   setStrat]   = useState({ ema_stack_scalper: true, spike_scalper: true, round_number_reactor: true, london_liquidity_sweep: true, asian_range_breakout: true, ict_logic: true });
  const [tg,      setTg]      = useState({ bot_token: "", chat_id: "" });
  const [tw,      setTw]      = useState({ enabled: false, bearer_token: "", api_key: "", api_secret: "", accounts_to_watch: [] });
  const [keys,    setKeys]    = useState({ finnhub_key: "", trading_economics_key: "", benzinga_key: "" });

  // Populate from loaded config
  useEffect(() => {
    if (!cfg) return;
    if (cfg.bot)       setBot(b   => ({ ...b,   ...cfg.bot }));
    if (cfg.risk)      setRisk(r  => ({ ...r,   ...cfg.risk }));
    if (cfg.confluence)setConf(c  => ({ ...c,   ...cfg.confluence }));
    if (cfg.technical) setTech(t  => ({ ...t,   ...cfg.technical }));
    if (cfg.news)      setNews(n  => ({ ...n,   ...cfg.news }));
    if (cfg.strategies)setStrat(s => ({ ...s,   ...cfg.strategies }));
    if (cfg.telegram)  setTg(t   => ({ ...t,   ...cfg.telegram }));
    if (cfg.twitter)   setTw(t   => ({ ...t,   ...cfg.twitter }));
  }, [cfg]);

  async function save() {
    setSaving(true); setError(null);
    try {
      const updates = [
        ["bot.mode",                          bot.mode],
        ["bot.paper_trading",                 String(bot.paper_trading)],
        ["risk.risk_per_trade",               String(risk.risk_per_trade)],
        ["risk.max_daily_loss",               String(risk.max_daily_loss)],
        ["risk.max_daily_profit",             String(risk.max_daily_profit)],
        ["risk.max_trades_per_day",           String(risk.max_trades_per_day)],
        ["risk.max_consecutive_losses",       String(risk.max_consecutive_losses)],
        ["risk.cooldown_after_loss_minutes",  String(risk.cooldown_after_loss_minutes)],
        ["risk.max_spread_points",            String(risk.max_spread_points)],
        ["confluence.min_score_to_trade",     String(conf.min_score_to_trade)],
        ["confluence.min_score_alert_only",   String(conf.min_score_alert_only)],
        ["confluence.min_score_priority",     String(conf.min_score_priority)],
        ["technical.ema_fast",                String(tech.ema_fast)],
        ["technical.adx_min",                 String(tech.adx_min)],
        ["news.enabled",                      String(news.enabled)],
        ["news.blackout_before_minutes",      String(news.blackout_before_minutes)],
        ["news.blackout_after_minutes",       String(news.blackout_after_minutes)],
      ];
      for (const [key, value] of updates) {
        await api.updateConfig(key, value);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const R  = (key) => (val) => setRisk(r => ({ ...r, [key]: val }));
  const C  = (key) => (val) => setConf(c => ({ ...c, [key]: val }));
  const T  = (key) => (val) => setTech(t => ({ ...t, [key]: val }));
  const N  = (key) => (val) => setNews(n => ({ ...n, [key]: val }));
  const S  = (key) => (val) => setStrat(s => ({ ...s, [key]: val }));

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">

      {/* Save bar */}
      <div className="flex items-center justify-between bg-gray-900/60 border border-gray-800 rounded-xl px-5 py-3">
        <div>
          <p className="text-white font-semibold text-sm">Configuration</p>
          <p className="text-gray-500 text-xs">Changes are applied immediately to the running backend</p>
        </div>
        <div className="flex items-center gap-3">
          {error  && <p className="text-red-400 text-xs">{error}</p>}
          {saved  && <p className="text-green-400 text-xs">✓ Saved</p>}
          <button onClick={save} disabled={saving}
            className="px-5 py-2 bg-yellow-500 hover:bg-yellow-400 text-black font-bold rounded-lg text-sm transition-colors disabled:opacity-50">
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>

      {/* BOT MODE */}
      <Section title="Bot Mode & Safety" icon="🤖">
        <Field label="Trading Mode" hint="Full Auto requires score ≥ min_score_to_trade">
          <Select value={bot.mode} onChange={v => setBot(b => ({ ...b, mode: v }))} options={[
            { value: "alert_only", label: "Alert Only — signals via Telegram, no execution" },
            { value: "semi_auto",  label: "Semi-Auto — Telegram approval before each trade" },
            { value: "full_auto",  label: "Full Auto — executes automatically" },
          ]} />
        </Field>
        <Field label="Paper Trading" hint="No real orders sent to broker">
          <Toggle value={bot.paper_trading} onChange={v => setBot(b => ({ ...b, paper_trading: v }))} label="Paper Trading Mode" />
        </Field>
      </Section>

      {/* RISK */}
      <Section title="Risk Management" icon="🛡️">
        <Field label="Risk per Trade (%)" hint="% of account balance. Max recommended: 1%">
          <NumberInput value={risk.risk_per_trade} onChange={R("risk_per_trade")} min={0.1} max={2} step={0.05} />
        </Field>
        <Field label="Max Daily Loss (%)" hint="Hard stop — no new trades after this loss">
          <NumberInput value={risk.max_daily_loss} onChange={R("max_daily_loss")} min={0.5} max={10} step={0.5} />
        </Field>
        <Field label="Max Daily Profit (%)" hint="Lock profits — stop trading after target hit">
          <NumberInput value={risk.max_daily_profit} onChange={R("max_daily_profit")} min={1} max={20} step={0.5} />
        </Field>
        <Field label="Max Trades per Day">
          <NumberInput value={risk.max_trades_per_day} onChange={R("max_trades_per_day")} min={1} max={20} step={1} />
        </Field>
        <Field label="Max Consecutive Losses" hint="Pause trading after N losses in a row">
          <NumberInput value={risk.max_consecutive_losses} onChange={R("max_consecutive_losses")} min={1} max={10} step={1} />
        </Field>
        <Field label="Cooldown after Loss (min)" hint="Wait before next trade after a loss">
          <NumberInput value={risk.cooldown_after_loss_minutes} onChange={R("cooldown_after_loss_minutes")} min={0} max={120} step={5} />
        </Field>
        <Field label="Max Spread (points)" hint="Skip trade if spread too wide">
          <NumberInput value={risk.max_spread_points} onChange={R("max_spread_points")} min={10} max={100} step={5} />
        </Field>
        <Field label="Break-Even at R" hint="Move SL to entry after X×R profit">
          <NumberInput value={risk.break_even_at_r} onChange={R("break_even_at_r")} min={0.5} max={3} step={0.25} />
        </Field>
        <Field label="Trailing Stop after TP1">
          <Toggle value={risk.trailing_stop_after_tp1} onChange={R("trailing_stop_after_tp1")} label="Enable trailing stop" />
        </Field>
      </Section>

      {/* CONFLUENCE */}
      <Section title="Confluence Score Thresholds" icon="📊">
        <Field label="Alert Only (min score)" hint="Show signal in Telegram but don't execute">
          <NumberInput value={conf.min_score_alert_only} onChange={C("min_score_alert_only")} min={0} max={100} step={1} />
        </Field>
        <Field label="Execute Trade (min score)" hint="Minimum score to open a trade">
          <NumberInput value={conf.min_score_to_trade} onChange={C("min_score_to_trade")} min={0} max={100} step={1} />
        </Field>
        <Field label="Priority Trade (min score)" hint="★ High-priority — larger position allowed">
          <NumberInput value={conf.min_score_priority} onChange={C("min_score_priority")} min={0} max={100} step={1} />
        </Field>
        {/* Visual scale */}
        <div className="md:col-span-2">
          <div className="flex items-center gap-0 rounded-lg overflow-hidden text-xs font-medium h-8">
            <div className="flex-1 bg-gray-700 text-gray-400 flex items-center justify-center">0–{conf.min_score_alert_only - 1} No action</div>
            <div className="flex-1 bg-blue-500/30 text-blue-300 flex items-center justify-center">{conf.min_score_alert_only}–{conf.min_score_to_trade - 1} Alert</div>
            <div className="flex-1 bg-green-500/30 text-green-300 flex items-center justify-center">{conf.min_score_to_trade}–{conf.min_score_priority - 1} Trade</div>
            <div className="flex-1 bg-yellow-500/30 text-yellow-300 flex items-center justify-center">{conf.min_score_priority}+ Priority ★</div>
          </div>
        </div>
      </Section>

      {/* TECHNICAL */}
      <Section title="Technical Indicators" icon="📈">
        <Field label="EMA Fast period"><NumberInput value={tech.ema_fast} onChange={T("ema_fast")} min={1} max={50} step={1} /></Field>
        <Field label="EMA Mid period"><NumberInput value={tech.ema_mid} onChange={T("ema_mid")} min={1} max={100} step={1} /></Field>
        <Field label="EMA Slow period"><NumberInput value={tech.ema_slow} onChange={T("ema_slow")} min={1} max={200} step={1} /></Field>
        <Field label="ADX Minimum" hint="Trend strength filter — no trade below this"><NumberInput value={tech.adx_min} onChange={T("adx_min")} min={10} max={50} step={1} /></Field>
        <Field label="ATR Period"><NumberInput value={tech.atr_period} onChange={T("atr_period")} min={5} max={50} step={1} /></Field>
        <Field label="Spike ATR Multiplier" hint="Candle > N×ATR = spike detected"><NumberInput value={tech.atr_spike_multiplier} onChange={T("atr_spike_multiplier")} min={1} max={5} step={0.1} /></Field>
      </Section>

      {/* STRATEGIES */}
      <Section title="Strategy Toggle" icon="⚡">
        {Object.entries(strat).map(([k, v]) => (
          <Field key={k} label={k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}>
            <Toggle value={v} onChange={S(k)} label={v ? "Enabled" : "Disabled"} />
          </Field>
        ))}
      </Section>

      {/* NEWS */}
      <Section title="News Filter" icon="📰">
        <Field label="News Filter Enabled">
          <Toggle value={news.enabled} onChange={N("enabled")} label="Block trades during news" />
        </Field>
        <Field label="Blackout Before Event (min)">
          <NumberInput value={news.blackout_before_minutes} onChange={N("blackout_before_minutes")} min={0} max={60} step={5} />
        </Field>
        <Field label="Blackout After Event (min)">
          <NumberInput value={news.blackout_after_minutes} onChange={N("blackout_after_minutes")} min={0} max={60} step={5} />
        </Field>
        <Field label="News Reaction Mode" hint="Allow trades on big macro surprises">
          <Toggle value={news.reaction_mode_enabled} onChange={N("reaction_mode_enabled")} label="Enable reaction trades" />
        </Field>
      </Section>

      {/* TELEGRAM */}
      <Section title="Telegram" icon="✈️">
        <Field label="Bot Token" hint="From @BotFather">
          <Input value={tg.bot_token} onChange={v => setTg(t => ({ ...t, bot_token: v }))} secret placeholder="123456:ABC..." />
        </Field>
        <Field label="Chat ID" hint="From @userinfobot">
          <Input value={tg.chat_id} onChange={v => setTg(t => ({ ...t, chat_id: v }))} placeholder="-100123..." />
        </Field>
        <div className="md:col-span-2">
          <button onClick={() => api.telegramTest()}
            className="px-4 py-2 bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg text-sm hover:bg-blue-500/30 transition-colors">
            Send Test Message
          </button>
        </div>
      </Section>

      {/* TWITTER */}
      <Section title="Twitter / X" icon="🐦">
        <Field label="Twitter Module">
          <Toggle value={tw.enabled} onChange={v => setTw(t => ({ ...t, enabled: v }))} label="Enable Twitter monitoring" />
        </Field>
        <Field label="Bearer Token" hint="From developer.twitter.com">
          <Input value={tw.bearer_token} onChange={v => setTw(t => ({ ...t, bearer_token: v }))} secret placeholder="AAAA..." />
        </Field>
        <Field label="API Key">
          <Input value={tw.api_key} onChange={v => setTw(t => ({ ...t, api_key: v }))} secret />
        </Field>
        <Field label="API Secret">
          <Input value={tw.api_secret} onChange={v => setTw(t => ({ ...t, api_secret: v }))} secret />
        </Field>
        <TwitterAccounts accounts={tw.accounts_to_watch} onChange={v => setTw(t => ({ ...t, accounts_to_watch: v }))} />
      </Section>

      {/* API KEYS */}
      <Section title="News API Keys" icon="🔑">
        <Field label="Finnhub API Key" hint="Free tier at finnhub.io">
          <Input value={keys.finnhub_key} onChange={v => setKeys(k => ({ ...k, finnhub_key: v }))} secret placeholder="pk_..." />
        </Field>
        <Field label="Trading Economics Key" hint="tradingeconomics.com/api">
          <Input value={keys.trading_economics_key} onChange={v => setKeys(k => ({ ...k, trading_economics_key: v }))} secret />
        </Field>
        <Field label="Benzinga Key" hint="Optional premium news feed">
          <Input value={keys.benzinga_key} onChange={v => setKeys(k => ({ ...k, benzinga_key: v }))} secret />
        </Field>
      </Section>

      {/* Bottom save */}
      <div className="flex justify-end pb-6">
        <button onClick={save} disabled={saving}
          className="px-8 py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-black rounded-xl text-sm transition-colors disabled:opacity-50 shadow-lg shadow-yellow-500/20">
          {saving ? "Saving…" : "Save All Settings"}
        </button>
      </div>
    </div>
  );
}
