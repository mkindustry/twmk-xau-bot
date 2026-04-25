import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

function ScoreBreakdown({ breakdown }) {
  if (!breakdown) return null;
  const entries = Object.entries(breakdown);
  const maxVals = { market_structure: 20, ema_alignment: 15, atr_volatility: 10, valid_session: 10, liquidity_sweep: 15, fvg_order_block: 15, macro_news_sentiment: 15 };
  return (
    <div className="space-y-2">
      {entries.map(([k, v]) => {
        const max = maxVals[k] ?? 20;
        const pct = (v / max) * 100;
        const label = k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        return (
          <div key={k}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">{label}</span>
              <span className="text-white font-medium">{v}/{max}</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-yellow-600 to-yellow-400 rounded-full transition-all"
                   style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function SignalsTab() {
  const { data: sigData, loading, error, refetch } = usePolling(useCallback(() => api.signal(), []), 5000);
  const { data: rsn } = usePolling(useCallback(() => api.reasoning(), []), 5000);

  const signal = sigData?.signal;
  const score  = signal?.confluence_score ?? 0;
  const isBuy  = signal?.direction === "BUY";

  return (
    <div className="p-6 space-y-6">
      {/* Live signal header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-bold text-lg">Live Signal</h2>
          <p className="text-gray-500 text-xs">Refreshes every 5 seconds</p>
        </div>
        <button onClick={refetch}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 rounded-lg text-xs hover:border-yellow-500/40 transition-colors">
          ↻ Refresh
        </button>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl p-3">{error}</div>}

      {!signal && !loading && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-12 text-center">
          <p className="text-gray-600">No signal yet — waiting for setup conditions</p>
          <p className="text-gray-700 text-xs mt-2">The EA sends data to the backend on each M5 bar close</p>
        </div>
      )}

      {signal && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Signal card */}
          <div className={`bg-gray-900/60 border rounded-xl p-6 ${isBuy ? "border-green-500/30" : "border-red-500/30"}`}>
            <div className="flex items-start justify-between mb-5">
              <div>
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl font-black text-lg mb-2 ${isBuy ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                  {signal.direction} {isBuy ? "▲" : "▼"}
                </div>
                <p className="text-gray-300 font-medium">{signal.strategy}</p>
                <p className="text-gray-500 text-xs mt-1">{signal.session} · {signal.generated_at?.slice(0, 19).replace("T", " ")} UTC</p>
              </div>
              <div className="text-right">
                <p className={`text-5xl font-black leading-none ${score >= 85 ? "text-yellow-400" : score >= 75 ? "text-green-400" : "text-blue-400"}`}>
                  {score}
                </p>
                <p className="text-gray-600 text-xs mt-1">/ 100 score</p>
                {score >= 85 && <p className="text-yellow-400 text-xs font-bold">★ PRIORITY</p>}
              </div>
            </div>

            {/* Price levels */}
            <div className="grid grid-cols-2 gap-2 mb-5">
              {[
                { label: "Entry",  value: signal.entry?.toFixed(2),  cls: "text-white border-gray-600" },
                { label: "Stop Loss", value: signal.sl?.toFixed(2),  cls: "text-red-400 border-red-500/30" },
                { label: "TP 1",   value: signal.tp1?.toFixed(2),    cls: "text-green-400 border-green-500/30" },
                { label: "TP 2",   value: signal.tp2?.toFixed(2),    cls: "text-emerald-400 border-emerald-500/30" },
                { label: "TP 3",   value: signal.tp3?.toFixed(2),    cls: "text-yellow-400 border-yellow-500/30" },
                { label: "Signal ID", value: signal.signal_id,       cls: "text-gray-400 border-gray-700 text-xs" },
              ].map(({ label, value, cls }) => (
                <div key={label} className={`bg-gray-800/60 border rounded-lg p-3 ${cls.split(" ").find(c => c.startsWith("border"))}`}>
                  <p className="text-gray-500 text-xs mb-0.5">{label}</p>
                  <p className={`font-bold ${cls.split(" ").filter(c => !c.startsWith("border")).join(" ")}`}>{value ?? "—"}</p>
                </div>
              ))}
            </div>

            {/* R:R */}
            {signal.entry && signal.sl && signal.tp2 && (
              <div className="bg-gray-800/60 rounded-lg p-3 text-center">
                <p className="text-gray-500 text-xs">Risk/Reward (to TP2)</p>
                <p className="text-white font-bold text-lg">
                  {(Math.abs(signal.tp2 - signal.entry) / Math.abs(signal.sl - signal.entry)).toFixed(1)}R
                </p>
              </div>
            )}
          </div>

          {/* Score breakdown */}
          <div className="space-y-4">
            <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5">
              <p className="text-gray-400 text-xs uppercase tracking-widest mb-4">Score Breakdown</p>
              <ScoreBreakdown breakdown={signal.score_breakdown} />
            </div>

            {/* Reasoning */}
            {signal.reasoning && (
              <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5">
                <p className="text-gray-400 text-xs uppercase tracking-widest mb-3">AI Reasoning</p>
                <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                  {signal.reasoning}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
