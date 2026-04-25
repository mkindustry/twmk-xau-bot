// API client — reads backend URL from env (set in Netlify dashboard)
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function get(path) {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

async function post(path, body = {}) {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`);
  return r.json();
}

export const api = {
  health:        () => get("/health"),
  signal:        () => get("/signal/latest"),
  reasoning:     () => get("/trade/reasoning"),
  risk:          () => get("/risk/status"),
  news:          () => get("/news/latest"),
  tweets:        () => get("/tweets/latest"),
  journal:       () => get("/backtest/report"),
  config:        () => get("/config/current"),
  telegramTest:  () => post("/telegram/test"),
  killSwitch:    (on) => post(`/kill_switch?activate=${on}`),
  updateConfig:  (key, value) => post("/config/update", { key, value }),
};
