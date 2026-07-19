import React, { useMemo, useState } from "react";

/*
  WHITELIGHT — 🤖 SYSTEMATIC PIPELINE control center  (v2, dependency-free)
  ---------------------------------------------------------------------
  Why v2: the previous version imported `recharts` and used Tailwind's
  arbitrary-value class syntax (text-[10px], bg-[#101317], etc). Both
  only work if your build already has that exact tooling configured —
  if either was missing, you'd get a build error or a blank/unstyled
  render with no obvious cause. This version has ZERO external
  dependencies beyond React itself: no Tailwind, no chart library, no
  CSS framework assumptions. All styling is a single scoped <style>
  block (class-prefixed "wl-" so it can't collide with existing CSS),
  and the equity curve is hand-rolled SVG using the same technique as
  the risk gauges below.

  If this STILL doesn't render correctly, the likely causes narrow to:
    1. Your build doesn't support JSX at all in this file location
       (wrong extension, or a webpack/vite config that excludes this
       path) — check how your other .jsx files under frontend/ are
       wired into the build, and put this file in the same location.
    2. A parent container is clipping/hiding it (check for a fixed
       height=0 wrapper, `overflow: hidden`, or a CSS reset that hits
       the "wl-root" class).
    3. It's mounted but nothing imports/renders <WhiteLightPanel />
       anywhere in your route tree.
    That's a much shorter, more diagnosable list than "recharts version
    mismatch" or "Tailwind content globs don't include this file."

  Scope note (unchanged): this is ONLY the automated Alpaca-connected
  control center. The separate manual "Options" journal tab keeps its
  own existing data/schema untouched — this file doesn't touch it.

  Signature element (unchanged): the automatic circuit breaker
  (read-only, tripped by the 7d/15% drawdown rule) and a separate
  MANUAL kill switch the operator controls directly. They are
  independent flags on purpose — see manual_pause vs lockdown_active
  in execution.py. An on-demand order ticket routes through the same
  risk-checked order path as automated trades.

  New in this version: a Pillars & Regime strip wired to src/scoring.py
  and src/regime.py — shows Trend/Momentum/Macro pillar scores and the
  named decision (e.g. "EXIT / TRIM", "RE-ENTRY") for the currently
  selected symbol, so the operator can see WHY the pipeline is (or
  isn't) willing to act, not just what it did.
*/

const COLORS = {
  bg: "#0B0D0F", panel: "#14171A", panelAlt: "#101317", border: "#24282D",
  amber: "#FFB000", blue: "#5B8DB8", red: "#E5484D", green: "#3FB27F",
  text: "#E8E6E1", muted: "#7D848D",
};

// ---------------------------------------------------------------- API config
// WIRE: point this at wherever src/api.py is actually running. GitHub Pages
// (which hosts this frontend) cannot run Python itself — this MUST be a
// separately-hosted URL. See the deployment note at the top of api.py.
const API_BASE = (typeof window !== "undefined" && window.WHITELIGHT_API_BASE) || "http://127.0.0.1:8000";
const API_KEY = (typeof window !== "undefined" && window.WHITELIGHT_API_KEY) || "";

async function apiGet(path) {
  const headers = {};
  if (API_KEY) headers['X-API-Key'] = API_KEY;
  const res = await fetch(`${API_BASE}${path}`, { headers, mode: 'cors' });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (API_KEY) headers['X-API-Key'] = API_KEY;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    mode: 'cors',
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${path} -> ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------- styles

function PanelStyles() {
  return (
    <style>{`
      .wl-root { background:${COLORS.bg}; color:${COLORS.text}; min-height:100vh; width:100%;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif; }
      .wl-container { max-width:1440px; margin:0 auto; padding:16px; }
      .wl-mono { font-family:ui-monospace,"SF Mono","IBM Plex Mono",Menlo,Consolas,monospace;
        font-variant-numeric:tabular-nums; }
      .wl-card { border:1px solid ${COLORS.border}; background:${COLORS.panel}; border-radius:10px; padding:16px; }
      .wl-label { font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:${COLORS.muted}; }
      .wl-row { display:flex; align-items:center; flex-wrap:wrap; gap:16px; }
      .wl-row-between { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; }
      .wl-statusbar { margin-bottom:16px; }
      .wl-grid2 { display:grid; grid-template-columns:1.6fr 1fr; gap:16px; margin-bottom:16px; }
      @media (max-width:900px) { .wl-grid2 { grid-template-columns:1fr; } }
      .wl-table { width:100%; border-collapse:collapse; }
      .wl-table th { text-align:left; font-weight:400; text-transform:uppercase; letter-spacing:0.08em;
        color:${COLORS.muted}; font-size:11px; padding:8px 16px; }
      .wl-table td { padding:8px 16px; font-size:12px; border-top:1px solid #1B1E22; }
      .wl-tab { padding:8px 16px; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; background:${COLORS.panelAlt}; color:${COLORS.text}; border:none; border-bottom:2px solid transparent; cursor:pointer; }
.wl-tab.active { border-bottom-color:${COLORS.amber}; color:${COLORS.amber}; }
      .wl-btn { padding:6px 12px; border-radius:6px; font-size:11px; font-weight:600; letter-spacing:0.04em;
        cursor:pointer; border:1px solid ${COLORS.border}; background:${COLORS.panelAlt}; color:${COLORS.muted}; }
      .wl-btn:disabled { opacity:0.3; cursor:not-allowed; }
      .wl-input { background:${COLORS.panelAlt}; border:1px solid ${COLORS.border}; border-radius:4px;
        padding:6px 8px; font-size:12px; color:${COLORS.text}; width:100%; box-sizing:border-box; }
      .wl-input:focus { outline:none; border-color:${COLORS.amber}; }
      .wl-orderGrid { display:grid; grid-template-columns:repeat(2,1fr); gap:8px; align-items:end; }
      @media (min-width:700px) { .wl-orderGrid { grid-template-columns:repeat(5,1fr); } }
      .wl-pillars { display:flex; gap:24px; flex-wrap:wrap; }
      .wl-pillar-chip { display:flex; flex-direction:column; align-items:center; gap:2px;
        border:1px solid ${COLORS.border}; border-radius:8px; padding:8px 14px; min-width:76px; }
    `}</style>
  );
}

// ---------------------------------------------------------------- mock data

function useMockData() {
  return useMemo(() => {
    const days = 120;
    const start = 100000;
    let equity = start;
    const curve = [];
    const now = new Date();
    for (let i = days; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const drift = Math.sin(i / 14) * 300 + (Math.random() - 0.48) * 900;
      equity = Math.max(equity + drift, start * 0.75);
      curve.push({ date: d.toISOString().slice(5, 10), equity: Math.round(equity) });
    }
    const peak7d = Math.max(...curve.slice(-7).map((p) => p.equity));
    const current = curve[curve.length - 1].equity;
    const drawdown7d = (current / peak7d - 1) * 100;

    return {
      lockdownActive: false,
      equityCurve: curve,
      currentEquity: current,
      dayPnl: curve[curve.length - 1].equity - curve[curve.length - 2].equity,
      drawdown7d,
      drawdownLimit: 15,
      marginHeat: 42,
      netDeltaPct: 12,
      positions: [
        { symbol: "AAPL", type: "vertical put credit", qty: 3, delta: -0.18, dte: 24, pnl: 214.5 },
        { symbol: "SPY", type: "iron condor", qty: 2, delta: 0.04, dte: 31, pnl: -58.2 },
        { symbol: "MSFT", type: "equity", qty: 40, delta: 1.0, dte: null, pnl: 611.0 },
      ],
      trades: [
        { time: "09:41", symbol: "AAPL", side: "SELL", qty: 3, price: 1.85, riskPct: 0.6, pnl: 214.5 },
        { time: "10:15", symbol: "SPY", side: "SELL", qty: 2, price: 2.10, riskPct: 0.9, pnl: -58.2 },
        { time: "11:02", symbol: "MSFT", side: "BUY", qty: 40, price: 412.3, riskPct: 1.2, pnl: 611.0 },
      ],
      options: [
    { symbol: "AAPL", type: "call", qty: 2, strike: 150, exp: "2024-12-20", premium: 2.5, pnl: 30 },
    { symbol: "SPY", type: "put", qty: 1, strike: 420, exp: "2024-11-15", premium: 1.8, pnl: -10 },
  ],
      scorecard: {
        symbol: "AAPL",
        trend: 2, momentum: -1, macro: 1, total: 2,
        decision: "HOLD (under review)",
        rationale: "Weak momentum, no full exit trigger yet.",
      },
    };
  }, []);
}

// ---------------------------------------------------------------- live data

function useLiveState(mock) {
  // Tries the real API on mount and every 10s; falls back to mock data
  // (and flags apiOnline=false) if the API isn't reachable — so this
  // component still renders something useful even before api.py is
  const [live, setLive] = useState({ apiOnline: false, error: null,
    state: null, positions: null, signals: null, ingestion: null, options: null });

  React.useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const [state, positions] = await Promise.all([apiGet("/api/state"), apiGet("/api/positions")]);
        let signals = null, ingestion = null, options = null, trades = null;
        // try { signals = await apiGet("/api/signals"); } catch (_) { /* not wired yet, ok */ }
        // try { ingestion = await apiGet("/api/ingestion/status"); } catch (_) { /* not wired yet, ok */ }
        // try { options = await apiGet("/api/options"); } catch (_) { /* not wired yet, ok */ }
        try { trades = await apiGet("/api/trades"); } catch (_) { /* not wired yet, ok */ }
        if (!cancelled) setLive({ apiOnline: true, error: null, state, positions, signals, ingestion, options, trades });
      } catch (e) {
        if (!cancelled) setLive((prev) => ({ ...prev, apiOnline: false, error: String(e) }));
      }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return live;
}

// ---------------------------------------------------------------- primitives

const fmt$ = (n) => (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

function EquitySpark({ data, width = 560, height = 200 }) {
  if (!data || data.length < 2) return null;
  const values = data.map((d) => d.equity);
  const min = Math.min(...values), max = Math.max(...values);
  const pad = (max - min) * 0.08 || 1;
  const yMin = min - pad, yMax = max + pad;
  const x = (i) => (i / (data.length - 1)) * (width - 24) + 12;
  const y = (v) => height - 20 - ((v - yMin) / (yMax - yMin || 1)) * (height - 40);
  const path = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(d.equity).toFixed(1)}`).join(" ");
  const baseline = data[0].equity;
  const step = Math.max(1, Math.floor(data.length / 6));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height}>
      <line x1="12" x2={width - 12} y1={y(baseline)} y2={y(baseline)} stroke={COLORS.border} strokeDasharray="3 3" />
      <path d={path} fill="none" stroke={COLORS.amber} strokeWidth="1.75" />
      {data.map((d, i) => (i % step === 0 || i === data.length - 1) ? (
        <text key={i} x={x(i)} y={height - 4} fontSize="9" fill={COLORS.muted} textAnchor="middle" className="wl-mono">
          {d.date}
        </text>
      ) : null)}
    </svg>
  );
}

function RadialGauge({ label, value, max, unit = "%", sub }) {
  const pct = Math.min(Math.abs(value) / max, 1);
  const angle = -140 + pct * 280;
  const color = pct > 0.75 ? COLORS.red : pct > 0.5 ? COLORS.amber : COLORS.blue;
  const r = 42, cx = 50, cy = 50;
  const toXY = (deg) => {
    const rad = (deg - 90) * (Math.PI / 180);
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  };
  const [x1, y1] = toXY(-140);
  const [x2, y2] = toXY(140);
  const [nx, ny] = toXY(angle);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg viewBox="0 0 100 92" width="96" height="96">
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`} fill="none" stroke={COLORS.border} strokeWidth="6" strokeLinecap="round" />
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${pct > 0.5 ? 1 : 0} 1 ${nx} ${ny}`} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="3" fill={color} />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="2" />
        <text x="50" y="52" textAnchor="middle" fontSize="15" fontWeight="600" fill={COLORS.text} className="wl-mono">
          {value.toFixed(0)}{unit}
        </text>
      </svg>
      <div className="wl-label">{label}</div>
      {sub && <div style={{ fontSize: 10, color: COLORS.muted }}>{sub}</div>}
    </div>
  );
}

function BreakerSwitch({ active }) {
  return (
    <div className="wl-row" style={{ gap: 12 }}>
      <div style={{ position: "relative", width: 56, height: 32, borderRadius: 999, border: `1px solid ${COLORS.border}`,
        background: COLORS.panelAlt, padding: 4, boxShadow: "inset 0 2px 4px rgba(0,0,0,0.6)" }}>
        <div style={{
          width: 24, height: 24, borderRadius: "50%", transition: "transform .3s",
          transform: active ? "translateX(24px)" : "translateX(0)",
          background: active ? "radial-gradient(circle at 35% 30%, #ff8686, #E5484D)" : "radial-gradient(circle at 35% 30%, #ffe08a, #FFB000)",
          boxShadow: active ? "0 0 10px #E5484D99" : "0 0 10px #FFB00099",
        }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: active ? COLORS.red : COLORS.amber }}>
          {active ? "LOCKDOWN ENGAGED" : "SYSTEM ARMED"}
        </span>
        <span style={{ fontSize: 10, color: COLORS.muted }}>
          {active ? "auto breaker: orders purged" : "7d drawdown breaker monitoring"}
        </span>
      </div>
    </div>
  );
}

function ManualKillSwitch({ paused, onToggle }) {
  return (
    <button onClick={onToggle} className="wl-row" style={{
      gap: 8, padding: "8px 12px", borderRadius: 6, cursor: "pointer",
      border: `1px solid ${paused ? COLORS.red : COLORS.border}`,
      background: paused ? "#2A1414" : COLORS.panelAlt,
      color: paused ? COLORS.red : COLORS.muted, fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
    }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: paused ? COLORS.red : COLORS.green,
        boxShadow: paused ? `0 0 6px ${COLORS.red}` : `0 0 6px ${COLORS.green}` }} />
      {paused ? "RESUME TRADING" : "PAUSE TRADING"}
    </button>
  );
}

function OrderTicket({ onSubmit }) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("BUY");
  const [qty, setQty] = useState("");
  const [orderType, setOrderType] = useState("MARKET");
  const [limitPrice, setLimitPrice] = useState("");
  const canSubmit = symbol.trim() !== "" && Number(qty) > 0 && (orderType === "MARKET" || Number(limitPrice) > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit?.({ symbol: symbol.toUpperCase(), side, qty: Number(qty), orderType, limitPrice: Number(limitPrice) || null });
    setSymbol(""); setQty(""); setLimitPrice("");
  };

  return (
    <div className="wl-card">
      <div className="wl-label" style={{ marginBottom: 12 }}>Manual Order Ticket · On-Demand</div>
      <div className="wl-orderGrid">
        <div>
          <label className="wl-label">Symbol</label>
          <input className="wl-input wl-mono" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="AAPL" />
        </div>
        <div>
          <label className="wl-label">Side</label>
          <select className="wl-input wl-mono" value={side} onChange={(e) => setSide(e.target.value)}>
            <option>BUY</option><option>SELL</option>
          </select>
        </div>
        <div>
          <label className="wl-label">Qty</label>
          <input className="wl-input wl-mono" type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="0" />
        </div>
        <div>
          <label className="wl-label">Type</label>
          <select className="wl-input wl-mono" value={orderType} onChange={(e) => setOrderType(e.target.value)}>
            <option value="MARKET">MARKET</option><option value="LIMIT">LIMIT</option>
          </select>
        </div>
        {orderType === "LIMIT" ? (
          <div>
            <label className="wl-label">Limit Px</label>
            <input className="wl-input wl-mono" type="number" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} placeholder="0.00" />
          </div>
        ) : (
          <button onClick={handleSubmit} disabled={!canSubmit} className="wl-btn"
            style={{ color: side === "BUY" ? COLORS.green : COLORS.red, borderColor: side === "BUY" ? COLORS.green : COLORS.red }}>
            SUBMIT {side}
          </button>
        )}
      </div>
      {orderType === "LIMIT" && (
        <div style={{ marginTop: 8 }}>
          <button onClick={handleSubmit} disabled={!canSubmit} className="wl-btn"
            style={{ color: side === "BUY" ? COLORS.green : COLORS.red, borderColor: side === "BUY" ? COLORS.green : COLORS.red }}>
            SUBMIT {side}
          </button>
        </div>
      )}
      <div style={{ fontSize: 10, color: COLORS.muted, marginTop: 8 }}>
        routes through the same Alpaca order path + risk checks as automated trades
      </div>
    </div>
  );
}

function PillarStrip({ scorecard }) {
  if (!scorecard) return null;
  const chip = (label, val) => (
    <div className="wl-pillar-chip">
      <div className="wl-label">{label}</div>
      <div className="wl-mono" style={{ fontSize: 16, fontWeight: 600, color: val > 0 ? COLORS.green : val < 0 ? COLORS.red : COLORS.text }}>
        {val > 0 ? "+" : ""}{val}
      </div>
    </div>
  );
  return (
    <div className="wl-card" style={{ marginBottom: 16 }}>
      <div className="wl-row-between">
        <div>
          <div className="wl-label">Pillars &amp; Regime · {scorecard.symbol}</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            <span style={{ color: COLORS.amber, fontWeight: 600 }}>{scorecard.decision}</span>
            <span style={{ color: COLORS.muted }}> — {scorecard.rationale}</span>
          </div>
        </div>
        <div className="wl-pillars">
          {chip("Trend", scorecard.trend)}
          {chip("Momentum", scorecard.momentum)}
          {chip("Macro", scorecard.macro)}
          {chip("Total", scorecard.total)}
        </div>
      </div>
    </div>
  );
}

function IngestionStatusCard({ ingestion, apiOnline }) {
  if (!apiOnline) {
    return (
      <div className="wl-card">
        <div className="wl-label" style={{ marginBottom: 8 }}>Data Ingestion Engine</div>
        <div style={{ fontSize: 12, color: COLORS.red }}>API unreachable — cannot report feed status.</div>
        <div style={{ fontSize: 10, color: COLORS.muted, marginTop: 4 }}>
          Set window.WHITELIGHT_API_BASE to your running api.py instance.
        </div>
      </div>
    );
  }
  const sources = ingestion?.sources || [];
  return (
    <div className="wl-card">
      <div className="wl-label" style={{ marginBottom: 8 }}>Data Ingestion Engine</div>
      {sources.length === 0 ? (
        <div style={{ fontSize: 12, color: COLORS.muted }}>No feed status reported yet.</div>
      ) : sources.map((s, i) => (
        <div key={i} className="wl-row-between" style={{ padding: "4px 0", fontSize: 12 }}>
          <span>{s.name}</span>
          <span className="wl-mono" style={{
            color: s.status === "ok" ? COLORS.green : s.status === "error" ? COLORS.red : COLORS.muted,
          }}>
            {s.last_success ? new Date(s.last_success * 1000).toLocaleTimeString() : s.status}
          </span>
        </div>
      ))}
    </div>
  );
}

function SignalsTable({ signals, apiOnline }) {
  if (!apiOnline) {
    return (
      <div className="wl-card">
        <div className="wl-label" style={{ marginBottom: 8 }}>📊 Signal Generation &amp; Calculations</div>
        <div style={{ fontSize: 12, color: COLORS.red }}>API unreachable — showing no live signals.</div>
      </div>
    );
  }
  const rows = signals?.signals || [];
  return (
    <div className="wl-card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "12px 16px" }} className="wl-label">
        📊 Signal Generation &amp; Calculations {signals?.regime ? `· regime: ${signals.regime}` : ""}
      </div>
      {rows.length === 0 ? (
        <div style={{ padding: "0 16px 16px", fontSize: 12, color: COLORS.muted }}>
          No signals reported — /api/signals not yet wired to scoring.py (see api.py).
        </div>
      ) : (
        <table className="wl-table wl-mono">
          <thead><tr>{["Symbol", "Trend", "Momentum", "Macro", "Total", "Decision"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.symbol}</td>
                <td style={{ color: r.trend > 0 ? COLORS.green : r.trend < 0 ? COLORS.red : COLORS.text }}>{r.trend > 0 ? "+" : ""}{r.trend}</td>
                <td style={{ color: r.momentum > 0 ? COLORS.green : r.momentum < 0 ? COLORS.red : COLORS.text }}>{r.momentum > 0 ? "+" : ""}{r.momentum}</td>
                <td style={{ color: r.macro > 0 ? COLORS.green : r.macro < 0 ? COLORS.red : COLORS.text }}>{r.macro > 0 ? "+" : ""}{r.macro}</td>
                <td>{r.total > 0 ? "+" : ""}{r.total}</td>
                <td style={{ color: COLORS.amber }}>{r.decision}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- main panel

export default function WhiteLightPanel() {
  const mock = useMockData();
  const live = useLiveState(mock);
  const [tab, setTab] = useState("positions");
  const [actionError, setActionError] = useState(null);

  // Prefer live data; fall back to mock so the panel still renders
  // something coherent before api.py is deployed anywhere.
  const s = live.apiOnline && live.state ? live.state : null;
  const currentEquity = s?.equity ?? mock.currentEquity;
  const dayPnl = s?.day_pnl ?? mock.dayPnl;
  const drawdown7d = s?.drawdown_7d_pct ?? mock.drawdown7d;
  const drawdownLimit = s?.drawdown_limit_pct ?? mock.drawdownLimit;
  const lockdownActive = s?.lockdown_active ?? mock.lockdownActive;
  const manualPause = s?.manual_pause ?? false;
  const positions = (live.apiOnline && live.positions?.positions) || mock.positions;
  const optionsData = (live.apiOnline && live.options) || mock.options;
  const [refreshedTrades, setRefreshedTrades] = useState(null);
  const trades = refreshedTrades || (live.apiOnline && live.trades?.trades) || mock.trades;

  const handleTogglePause = async () => {
    setActionError(null);
    try {
      await apiPost("/api/pause", { paused: !manualPause });
    } catch (e) {
      setActionError(String(e));
    }
  };

  const handleOrderSubmit = async (order) => {
    setActionError(null);
    try {
      await apiPost("/api/order", {
        symbol: order.symbol,
        side: order.side,
        qty: order.qty,
        order_type: order.orderType,
        limit_price: order.limitPrice,
      });
      // Immediately fetch fresh trades to update the log
      const fresh = await apiGet("/api/trades");
      if (fresh && fresh.trades) {
        setRefreshedTrades(fresh.trades);
      }
    } catch (e) {
      setActionError(String(e));
    }
  };

  return (
    <div className="wl-root">
      <PanelStyles />
      <div className="wl-container">

        {!live.apiOnline && (
          <div className="wl-card" style={{ marginBottom: 16, borderColor: COLORS.red }}>
            <span style={{ color: COLORS.red, fontSize: 12, fontWeight: 600 }}>API unreachable</span>
            <span style={{ color: COLORS.muted, fontSize: 12 }}> — showing illustrative data. Point window.WHITELIGHT_API_BASE at a running api.py to go live.</span>
          </div>
        )}
        {actionError && (
          <div className="wl-card" style={{ marginBottom: 16, borderColor: COLORS.red }}>
            <span style={{ color: COLORS.red, fontSize: 12 }}>{actionError}</span>
          </div>
        )}

        <div className="wl-card wl-statusbar">
          <div className="wl-row-between">
            <div className="wl-row" style={{ gap: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.2em", color: COLORS.amber }}>WHITELIGHT</span>
              <span className="wl-label">🤖 systematic pipeline · live execution</span>
            </div>
            <div className="wl-row" style={{ gap: 28 }}>
              <div>
                <div className="wl-label">Equity</div>
                <div className="wl-mono" style={{ fontSize: 18 }}>{fmt$(currentEquity)}</div>
              </div>
              <div>
                <div className="wl-label">Day P&amp;L</div>
                <div className="wl-mono" style={{ fontSize: 18, color: dayPnl >= 0 ? COLORS.green : COLORS.red }}>
                  {dayPnl >= 0 ? "+" : ""}{fmt$(dayPnl)}
                </div>
              </div>
              <BreakerSwitch active={lockdownActive} />
              <div style={{ width: 1, height: 32, background: COLORS.border }} />
              <ManualKillSwitch paused={manualPause} onToggle={handleTogglePause} />
            </div>
          </div>
        </div>

        <PillarStrip scorecard={mock.scorecard} />

        <div className="wl-grid2">
          <IngestionStatusCard ingestion={live.ingestion} apiOnline={live.apiOnline} />
          <div className="wl-card">
            <div className="wl-label" style={{ marginBottom: 8 }}>Risk Instruments</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", placeItems: "center" }}>
              <RadialGauge label="7d Drawdown" value={Math.abs(drawdown7d)} max={drawdownLimit} sub={`limit ${drawdownLimit}%`} />
              <RadialGauge label="Margin Heat" value={mock.marginHeat} max={100} />
              <RadialGauge label="Net Delta" value={Math.abs(mock.netDeltaPct)} max={50} unit="" sub="Δ exposure" />
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <SignalsTable signals={live.signals} apiOnline={live.apiOnline} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <OrderTicket onSubmit={handleOrderSubmit} />
        </div>

        <div className="wl-card" style={{ marginBottom: 16 }}>
          <div className="wl-label" style={{ marginBottom: 8 }}>Equity Curve · 120d</div>
                    <EquitySpark />
          </div>

          <div className="wl-panel-wrapper">
            <div className="wl-card" style={{ padding: 0, overflow: "hidden" }}>
              {/* Tab buttons */}
              <div style={{ display: "flex", gap: 8 }}>
                {['positions', 'trade log'].map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    style={{
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: tab === t ? COLORS.amber : COLORS.text,
                      marginBottom: 4,
                      textAlign: "left",
                      padding: "4px 12px",
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
              
                
                  
                    

              
              {tab === "positions" ? (
                <table className="wl-table wl-mono">
                  <thead>
                    <tr>{["Symbol", "Structure", "Qty", "Delta", "DTE", "P&L"].map((h) => <th key={h}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {positions.map((p, i) => (
                      <tr key={i}>
                        <td>{p.symbol}</td>
                        <td style={{ color: COLORS.muted }}>{p.type}</td>
                        <td>{p.qty}</td>
                        <td>{p.delta.toFixed(2)}</td>
                        <td>{p.dte ?? "—"}</td>
                        <td style={{ color: p.pnl >= 0 ? COLORS.green : COLORS.red }}>{p.pnl >= 0 ? "+" : ""}{fmt$(p.pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table className="wl-table wl-mono">
                  <thead>
                    <tr>{["Time", "Symbol", "Side", "Qty", "Price", "Risk %", "P&L"].map((h) => <th key={h}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {trades.map((t, i) => (
                      <tr key={i}>
                        <td style={{ color: COLORS.muted }}>{t.time}</td>
                        <td>{t.symbol}</td>
                        <td style={{ color: t.side === "BUY" ? COLORS.blue : COLORS.amber }}>{t.side}</td>
                        <td>{t.qty}</td>
                        <td>{t.price.toFixed(2)}</td>
                        <td>{t.riskPct.toFixed(1)}%</td>
                        <td style={{ color: t.pnl >= 0 ? COLORS.green : COLORS.red }}>{t.pnl >= 0 ? "+" : ""}{fmt$(t.pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        <div style={{ fontSize: 10, color: COLORS.muted, marginTop: 16, textAlign: "center", letterSpacing: "0.02em" }}>
          {live.apiOnline ? "live · connected to api.py" : "dry-run mode · illustrative data"}
        </div>
      </div>
    </div>
  );
}
