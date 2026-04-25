import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

const BIAS_STYLE = {
  bullish: "text-green-400 bg-green-400/10 border-green-400/20",
  bearish: "text-red-400   bg-red-400/10   border-red-400/20",
  neutral: "text-gray-400  bg-gray-400/10  border-gray-400/20",
};

function ImpactBar({ score }) {
  const color = score >= 80 ? "bg-red-500" : score >= 60 ? "bg-yellow-500" : score >= 40 ? "bg-blue-500" : "bg-gray-600";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-800 rounded-full h-1.5 overflow-hidden">
        <div className={`h-1.5 rounded-full ${color} transition-all duration-500`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-8 text-right">{score}</span>
    </div>
  );
}

function TweetCard({ signal }) {
  const bias = BIAS_STYLE[signal.xau_bias] ?? BIAS_STYLE.neutral;
  const time = signal.created_at ? new Date(signal.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <div className="bg-gray-800/40 border border-gray-700/50 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300">
            {signal.account?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div>
            <p className="text-white text-sm font-medium">@{signal.account}</p>
            <p className="text-gray-500 text-xs">{time}</p>
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-bold ${bias}`}>
          {signal.xau_bias?.toUpperCase()}
        </span>
      </div>

      <p className="text-gray-300 text-sm leading-relaxed mb-3">{signal.text}</p>

      <div className="space-y-1.5">
        <ImpactBar score={signal.impact_score} />
        {signal.categories?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {signal.categories.map((c) => (
              <span key={c} className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{c}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function TweetsTab() {
  const { data, loading, error } = usePolling(useCallback(() => api.tweets(), []), 30000);

  const signals   = data?.signals ?? [];
  const bias      = data?.current_bias ?? "neutral";
  const aggregate = data?.aggregate_impact ?? 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className={`rounded-xl p-4 border ${bias === "bullish" ? "bg-green-500/10 border-green-500/30" : bias === "bearish" ? "bg-red-500/10 border-red-500/30" : "bg-gray-900/60 border-gray-800"}`}>
          <p className="text-gray-400 text-xs uppercase tracking-widest">Social XAU Bias</p>
          <p className={`text-2xl font-black mt-1 ${bias === "bullish" ? "text-green-400" : bias === "bearish" ? "text-red-400" : "text-gray-400"}`}>
            {bias.toUpperCase()}
          </p>
        </div>
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs uppercase tracking-widest">Aggregate Impact</p>
          <p className="text-2xl font-black text-white mt-1">{aggregate}<span className="text-gray-600 text-base">/100</span></p>
          <ImpactBar score={aggregate} />
        </div>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl p-3">{error}</div>}
      {loading && <div className="text-gray-500 text-sm">Loading tweets...</div>}

      {/* Tweet cards */}
      <div className="space-y-3">
        {signals.length === 0
          ? <div className="text-gray-600 text-sm text-center py-12">No tweets loaded — check X API keys in config</div>
          : signals.map((s, i) => <TweetCard key={i} signal={s} />)}
      </div>
    </div>
  );
}
