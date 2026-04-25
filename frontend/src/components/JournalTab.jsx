import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

function Stat({ label, value, color = "text-white" }) {
  return (
    <div className="bg-gray-800/60 rounded-xl p-4 text-center">
      <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value ?? "—"}</p>
    </div>
  );
}

const STATUS_STYLE = {
  TP1:    "text-green-400 bg-green-400/10",
  TP2:    "text-emerald-400 bg-emerald-400/10",
  TP3:    "text-yellow-400 bg-yellow-400/10",
  SL:     "text-red-400 bg-red-400/10",
  BE:     "text-blue-400 bg-blue-400/10",
  OPEN:   "text-purple-400 bg-purple-400/10",
  MANUAL: "text-gray-400 bg-gray-400/10",
};

export function JournalTab() {
  const { data, loading, error } = usePolling(useCallback(() => api.journal(), []), 30000);

  const trades  = data?.trades ?? [];
  const wr      = data?.win_rate_pct;
  const totalPnl = data?.total_pnl_usd;

  return (
    <div className="p-6 space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Total Trades" value={data?.closed_trades ?? 0} />
        <Stat label="Win Rate"     value={wr != null ? `${wr}%` : "—"} color={wr >= 50 ? "text-green-400" : "text-red-400"} />
        <Stat label="Total P&L"    value={totalPnl != null ? `${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}$` : "—"}
              color={totalPnl >= 0 ? "text-green-400" : "text-red-400"} />
        <Stat label="Avg Win"      value={data?.avg_win != null ? `+${data.avg_win.toFixed(2)}$` : "—"} color="text-green-400" />
      </div>

      {error && <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl p-3">{error}</div>}

      {/* Trade table */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <p className="text-gray-400 text-xs uppercase tracking-widest">Trade Journal</p>
          <p className="text-gray-600 text-xs">Last 50 trades</p>
        </div>

        {loading
          ? <div className="p-6 text-gray-500 text-sm">Loading journal...</div>
          : trades.length === 0
          ? <div className="p-6 text-gray-600 text-sm text-center">No trades recorded yet</div>
          : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Time", "Dir", "Strategy", "Entry", "Close", "SL", "TP1", "Score", "P&L", "Status"].map(h => (
                    <th key={h} className="text-left text-gray-500 text-xs px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...trades].reverse().map((t, i) => {
                  const pnl    = parseFloat(t.pnl ?? 0);
                  const st     = STATUS_STYLE[t.status] ?? STATUS_STYLE.MANUAL;
                  const isBuy  = t.direction === "BUY";
                  return (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                      <td className="px-4 py-3 text-gray-500 text-xs">{t.open_time?.slice(11, 16)}</td>
                      <td className={`px-4 py-3 font-bold ${isBuy ? "text-green-400" : "text-red-400"}`}>{t.direction}</td>
                      <td className="px-4 py-3 text-gray-300 text-xs max-w-[120px] truncate">{t.strategy}</td>
                      <td className="px-4 py-3 text-white">{parseFloat(t.entry).toFixed(2)}</td>
                      <td className="px-4 py-3 text-gray-300">{t.close_price ? parseFloat(t.close_price).toFixed(2) : "—"}</td>
                      <td className="px-4 py-3 text-red-400">{parseFloat(t.sl).toFixed(2)}</td>
                      <td className="px-4 py-3 text-green-400">{parseFloat(t.tp1).toFixed(2)}</td>
                      <td className="px-4 py-3 text-gray-300">{t.confluence_score}</td>
                      <td className={`px-4 py-3 font-bold ${pnl > 0 ? "text-green-400" : pnl < 0 ? "text-red-400" : "text-gray-400"}`}>
                        {pnl !== 0 ? `${pnl > 0 ? "+" : ""}${pnl.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${st}`}>{t.status}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
