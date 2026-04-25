import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

function StatCard({ label, value, sub, color = "text-white", border = "border-gray-800" }) {
  return (
    <div className={`bg-gray-900/60 border ${border} rounded-xl p-4 backdrop-blur`}>
      <p className="text-gray-500 text-xs uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value ?? "—"}</p>
      {sub && <p className="text-gray-500 text-xs mt-1">{sub}</p>}
    </div>
  );
}

function ScoreBar({ score, max = 100 }) {
  const pct = Math.min((score / max) * 100, 100);
  const color = score >= 85 ? "from-yellow-500 to-amber-400"
    : score >= 75 ? "from-green-500 to-emerald-400"
    : score >= 60 ? "from-blue-500 to-cyan-400"
    : "from-gray-600 to-gray-500";
  return (
    <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
      <div className={`h-2 rounded-full bg-gradient-to-r ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SignalCard({ signal }) {
  if (!signal) return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-6 flex items-center justify-center min-h-[200px]">
      <p className="text-gray-600 text-sm">No signal generated yet</p>
    </div>
  );

  const isBuy  = signal.direction === "BUY";
  const score  = signal.confluence_score;
  const isPrio = score >= 85;

  return (
    <div className={`bg-gray-900/60 border rounded-xl p-5 backdrop-blur ${isBuy ? "border-green-500/30" : "border-red-500/30"}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`px-3 py-1.5 rounded-lg font-black text-sm ${isBuy ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
            {signal.direction} {isBuy ? "▲" : "▼"}
          </div>
          <div>
            <p className="text-white font-bold">{signal.strategy}</p>
            <p className="text-gray-500 text-xs">{signal.session} · {signal.generated_at?.slice(11, 16)} UTC</p>
          </div>
          {isPrio && <span className="text-yellow-400 text-lg">★</span>}
        </div>
        <div className="text-right">
          <p className={`text-3xl font-black ${score >= 85 ? "text-yellow-400" : score >= 75 ? "text-green-400" : "text-blue-400"}`}>
            {score}<span className="text-gray-600 text-lg">/100</span>
          </p>
          <p className="text-gray-500 text-xs">Confluence</p>
        </div>
      </div>

      <ScoreBar score={score} />

      <div className="grid grid-cols-4 gap-3 mt-4">
        {[
          { l: "Entry",  v: signal.entry?.toFixed(2),  c: "text-white" },
          { l: "SL",     v: signal.sl?.toFixed(2),     c: "text-red-400" },
          { l: "TP1",    v: signal.tp1?.toFixed(2),    c: "text-green-400" },
          { l: "TP2",    v: signal.tp2?.toFixed(2),    c: "text-emerald-400" },
        ].map(({ l, v, c }) => (
          <div key={l} className="bg-gray-800/60 rounded-lg p-2 text-center">
            <p className="text-gray-500 text-xs">{l}</p>
            <p className={`font-bold text-sm ${c}`}>{v ?? "—"}</p>
          </div>
        ))}
      </div>

      {signal.reasoning && (
        <details className="mt-4">
          <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-200 select-none">
            View full reasoning ▸
          </summary>
          <pre className="mt-2 text-xs text-gray-400 whitespace-pre-wrap bg-gray-800/60 rounded-lg p-3 font-mono leading-relaxed">
            {signal.reasoning}
          </pre>
        </details>
      )}
    </div>
  );
}

function RiskGauge({ risk }) {
  if (!risk) return null;
  const pnl       = risk.pnl_usd ?? 0;
  const pnlPct    = risk.pnl_pct ?? 0;
  const canTrade  = risk.can_trade;
  const wins      = risk.wins ?? 0;
  const losses    = risk.losses ?? 0;
  const total     = wins + losses;
  const wr        = total > 0 ? ((wins / total) * 100).toFixed(0) : "—";

  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 backdrop-blur">
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-400 text-xs uppercase tracking-widest">Risk Status</p>
        <div className={`flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${canTrade ? "text-green-400 bg-green-400/10" : "text-red-400 bg-red-400/10"}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${canTrade ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
          {canTrade ? "CAN TRADE" : "BLOCKED"}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-gray-500 text-xs">Day P&L</p>
          <p className={`text-xl font-black ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
            {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}$
          </p>
          <p className="text-gray-600 text-xs">{pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-gray-500 text-xs">Win Rate</p>
          <p className="text-xl font-black text-white">{wr}%</p>
          <p className="text-gray-600 text-xs">{wins}W / {losses}L</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-gray-500 text-xs">Trades Today</p>
          <p className="text-xl font-black text-white">{risk.trades_opened ?? 0}</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-gray-500 text-xs">Consec. Losses</p>
          <p className={`text-xl font-black ${(risk.consecutive_losses ?? 0) >= 2 ? "text-red-400" : "text-white"}`}>
            {risk.consecutive_losses ?? 0}
          </p>
        </div>
      </div>

      {!canTrade && risk.block_reason && (
        <div className="mt-3 text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg p-2">
          ⛔ {risk.block_reason}
        </div>
      )}
    </div>
  );
}

export function DashboardTab() {
  const { data: signal } = usePolling(useCallback(() => api.signal(), []), 5000);
  const { data: risk }   = usePolling(useCallback(() => api.risk(), []), 5000);
  const { data: news }   = usePolling(useCallback(() => api.news(), []), 30000);

  const sig    = signal?.signal;
  const events = news?.upcoming?.slice(0, 4) ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Top stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Score"
          value={sig ? `${sig.confluence_score}/100` : "—"}
          sub={sig?.strategy}
          color={sig?.confluence_score >= 85 ? "text-yellow-400" : sig?.confluence_score >= 75 ? "text-green-400" : "text-blue-400"}
          border={sig ? "border-yellow-500/20" : "border-gray-800"}
        />
        <StatCard
          label="Direction"
          value={sig?.direction ?? "FLAT"}
          sub={sig?.session}
          color={sig?.direction === "BUY" ? "text-green-400" : sig?.direction === "SELL" ? "text-red-400" : "text-gray-500"}
        />
        <StatCard
          label="Day P&L"
          value={risk ? `${risk.pnl_usd >= 0 ? "+" : ""}${risk.pnl_usd?.toFixed(2)}$` : "—"}
          sub={`${risk?.pnl_pct >= 0 ? "+" : ""}${risk?.pnl_pct?.toFixed(2) ?? "0"}%`}
          color={risk?.pnl_usd >= 0 ? "text-green-400" : "text-red-400"}
        />
        <StatCard
          label="Blackout"
          value={news?.blackout ? "YES" : "CLEAR"}
          sub={news?.blackout ? "News window active" : "No news blackout"}
          color={news?.blackout ? "text-red-400" : "text-green-400"}
          border={news?.blackout ? "border-red-500/30" : "border-gray-800"}
        />
      </div>

      {/* Signal + Risk */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <SignalCard signal={sig} />
        </div>
        <RiskGauge risk={risk} />
      </div>

      {/* Upcoming news */}
      {events.length > 0 && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs uppercase tracking-widest mb-3">Upcoming Events</p>
          <div className="space-y-2">
            {events.map((e, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${e.impact === "HIGH" ? "bg-red-400" : e.impact === "MEDIUM" ? "bg-yellow-400" : "bg-gray-500"}`} />
                  <span className="text-white">{e.title}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-bold ${e.xau_bias === "bullish" ? "text-green-400" : e.xau_bias === "bearish" ? "text-red-400" : "text-gray-500"}`}>
                    {e.xau_bias?.toUpperCase()}
                  </span>
                  <span className="text-gray-500 text-xs">in {e.minutes_away?.toFixed(0)} min</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
