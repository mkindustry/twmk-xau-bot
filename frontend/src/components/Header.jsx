import { useState } from "react";
import { api } from "../api";

const MODE_COLORS = {
  alert_only: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
  semi_auto:  "text-blue-400  bg-blue-400/10  border-blue-400/30",
  full_auto:  "text-green-400 bg-green-400/10 border-green-400/30",
};

const SESSION_COLORS = {
  LONDON:   "text-yellow-300",
  "NEW YORK": "text-green-300",
  OVERLAP:  "text-orange-300",
  ASIAN:    "text-blue-300",
  CLOSED:   "text-gray-500",
};

export function Header({ health, onKillSwitch }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const mode     = health?.mode || "alert_only";
  const killed   = health?.kill_switch || false;
  const paper    = health?.paper_trading;
  const session  = health?.session || "CLOSED";

  async function handleKill() {
    if (!confirming) { setConfirming(true); return; }
    setBusy(true);
    try { await api.killSwitch(!killed); onKillSwitch?.(); }
    finally { setBusy(false); setConfirming(false); }
  }

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-500 to-amber-600 flex items-center justify-center shadow-lg shadow-yellow-500/20">
          <span className="text-black font-black text-sm">XAU</span>
        </div>
        <div>
          <p className="text-white font-bold text-sm leading-none">TRADESWITHMK</p>
          <p className="text-yellow-500/70 text-xs leading-none mt-0.5">XAU INTEL BOT</p>
        </div>
      </div>

      {/* Center badges */}
      <div className="flex items-center gap-3">
        {/* Connection */}
        <div className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${health ? "text-green-400 bg-green-400/10 border-green-400/30" : "text-red-400 bg-red-400/10 border-red-400/30"}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${health ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
          {health ? "CONNECTED" : "OFFLINE"}
        </div>

        {/* Mode */}
        <div className={`text-xs px-2.5 py-1 rounded-full border font-medium ${MODE_COLORS[mode] || MODE_COLORS.alert_only}`}>
          {mode.replace("_", " ").toUpperCase()}
        </div>

        {/* Paper */}
        {paper && (
          <div className="text-xs px-2.5 py-1 rounded-full border text-purple-400 bg-purple-400/10 border-purple-400/30 font-medium">
            PAPER
          </div>
        )}

        {/* Session */}
        <div className={`text-xs font-bold ${SESSION_COLORS[session] || "text-gray-500"}`}>
          {session}
        </div>
      </div>

      {/* Kill switch */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => api.telegramTest()}
          className="text-xs text-gray-400 hover:text-gray-200 px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
        >
          Test Telegram
        </button>

        {confirming && (
          <span className="text-xs text-red-400 animate-pulse">Confirm?</span>
        )}

        <button
          disabled={busy}
          onClick={handleKill}
          onBlur={() => setConfirming(false)}
          className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
            killed
              ? "text-green-400 border-green-500/50 bg-green-500/10 hover:bg-green-500/20"
              : confirming
              ? "text-red-300 border-red-500 bg-red-500/20 animate-pulse"
              : "text-red-400 border-red-500/50 bg-red-500/10 hover:bg-red-500/20"
          }`}
        >
          {killed ? "⏸ RESUME" : confirming ? "CONFIRM KILL?" : "⛔ KILL SWITCH"}
        </button>
      </div>
    </header>
  );
}
