import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

const IMPACT_STYLE = {
  HIGH:   { dot: "bg-red-400",    badge: "text-red-400 bg-red-400/10 border-red-400/20" },
  MEDIUM: { dot: "bg-yellow-400", badge: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20" },
  LOW:    { dot: "bg-gray-500",   badge: "text-gray-400 bg-gray-400/10 border-gray-400/20" },
};

const BIAS_STYLE = {
  bullish: "text-green-400 bg-green-400/10 border-green-400/20",
  bearish: "text-red-400   bg-red-400/10   border-red-400/20",
  neutral: "text-gray-400  bg-gray-400/10  border-gray-400/20",
};

function EventRow({ event }) {
  const imp  = IMPACT_STYLE[event.impact] ?? IMPACT_STYLE.LOW;
  const bias = BIAS_STYLE[event.xau_bias] ?? BIAS_STYLE.neutral;
  const time = event.time ? new Date(event.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-800/60 last:border-0">
      <div className="w-14 text-center">
        <p className="text-gray-400 text-xs">{time}</p>
        <p className="text-gray-600 text-xs">UTC</p>
      </div>

      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${imp.dot}`} />

      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-medium truncate">{event.title}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-gray-500 text-xs">{event.currency}</span>
          {event.actual   && <span className="text-xs text-green-400">A: {event.actual}</span>}
          {event.forecast && <span className="text-xs text-gray-400">F: {event.forecast}</span>}
          {event.previous && <span className="text-xs text-gray-500">P: {event.previous}</span>}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`text-xs px-2 py-0.5 rounded-full border ${imp.badge}`}>
          {event.impact}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${bias}`}>
          {event.xau_bias?.toUpperCase() || "—"}
        </span>
      </div>
    </div>
  );
}

export function NewsTab() {
  const { data, loading, error } = usePolling(useCallback(() => api.news(), []), 30000);

  const upcoming = data?.upcoming ?? [];
  const recent   = data?.events   ?? [];
  const macroBias = data?.macro_bias ?? "neutral";

  return (
    <div className="p-6 space-y-6">
      {/* Macro bias banner */}
      <div className={`rounded-xl p-4 border flex items-center justify-between ${
        macroBias === "bullish" ? "bg-green-500/10 border-green-500/30" :
        macroBias === "bearish" ? "bg-red-500/10   border-red-500/30"   :
        "bg-gray-800/60 border-gray-700"}`}>
        <div>
          <p className="text-gray-400 text-xs uppercase tracking-widest">Macro XAU Bias</p>
          <p className={`text-2xl font-black mt-1 ${macroBias === "bullish" ? "text-green-400" : macroBias === "bearish" ? "text-red-400" : "text-gray-400"}`}>
            {macroBias.toUpperCase()}
          </p>
        </div>
        <div className={`text-5xl opacity-20 ${macroBias === "bullish" ? "text-green-400" : macroBias === "bearish" ? "text-red-400" : "text-gray-600"}`}>
          {macroBias === "bullish" ? "▲" : macroBias === "bearish" ? "▼" : "—"}
        </div>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl p-3">{error}</div>}
      {loading && <div className="text-gray-500 text-sm">Loading news...</div>}

      {/* Upcoming events */}
      {upcoming.length > 0 && (
        <div className="bg-gray-900/60 border border-yellow-500/20 rounded-xl p-4">
          <p className="text-yellow-400 text-xs uppercase tracking-widest mb-3">⏰ Upcoming (next 4h)</p>
          {upcoming.map((e, i) => <EventRow key={i} event={e} />)}
        </div>
      )}

      {/* All events */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
        <p className="text-gray-400 text-xs uppercase tracking-widest mb-3">Economic Calendar</p>
        {recent.length === 0
          ? <p className="text-gray-600 text-sm">No events loaded</p>
          : recent.map((e, i) => <EventRow key={i} event={e} />)}
      </div>
    </div>
  );
}
