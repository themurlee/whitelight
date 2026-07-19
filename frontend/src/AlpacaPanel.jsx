import React, { useMemo, useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

/*
  WHITELIGHT — 🤖 SYSTEMATIC PIPELINE control center
  ------------------------------------------
  Tokens:
    bg          #0B0D0F   near-black warm charcoal (not pure black)
    panel       #14171A
    panel-alt   #101317
    border      #24282D   hairline
    amber       #FFB000   primary instrument accent
    blue        #5B8DB8   secondary / cool data accent
    red         #E5484D   danger / lockdown
    green       #3FB27F   ONLY for positive P&L — never decorative
    text        #E8E6E1
    text-muted  #7D848D
*/

const API_BASE = 'http://127.0.0.1:8000/api';

const fmt$ = (n) => (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
const fmtPct = (n, d = 1) => `${n >= 0 ? "+" : ""}${n.toFixed(d)}%`;

function RadialGauge({ label, value, max, unit = "%", danger = false, sub }) {
  const pct = Math.min(Math.abs(value) / max, 1);
  const angle = -140 + pct * 280; // -140deg..+140deg sweep
  const color = danger ? "#E5484D" : pct > 0.75 ? "#E5484D" : pct > 0.5 ? "#FFB000" : "#5B8DB8";
  const r = 42, cx = 50, cy = 50;
  const toXY = (deg) => {
    const rad = (deg - 90) * (Math.PI / 180);
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  };
  const [x1, y1] = toXY(-140);
  const [x2, y2] = toXY(140);
  const [nx, ny] = toXY(angle);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg viewBox="0 0 100 92" className="w-24 h-24">
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`}
              fill="none" stroke="#24282D" strokeWidth="6" strokeLinecap="round" />
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${pct > 0.5 ? 1 : 0} 1 ${nx} ${ny}`}
              fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="3" fill={color} />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="2" />
        <text x="50" y="52" textAnchor="middle" fontSize="15" fontFamily="ui-monospace, monospace"
              fill="#E8E6E1" fontWeight="600">
          {value.toFixed(0)}{unit}
        </text>
      </svg>
      <div className="text-[10px] tracking-widest uppercase text-[#7D848D]">{label}</div>
      {sub && <div className="text-[10px] text-[#7D848D]">{sub}</div>}
    </div>
  );
}

function BreakerSwitch({ active }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative w-14 h-8 rounded-full border border-[#24282D] bg-[#101317] p-1"
           style={{ boxShadow: "inset 0 2px 4px rgba(0,0,0,0.6)" }}>
        <div
          className="w-6 h-6 rounded-full transition-transform duration-300"
          style={{
            transform: active ? "translateX(24px)" : "translateX(0)",
            background: active
              ? "radial-gradient(circle at 35% 30%, #ff8686, #E5484D)"
              : "radial-gradient(circle at 35% 30%, #ffe08a, #FFB000)",
            boxShadow: active ? "0 0 10px #E5484D99" : "0 0 10px #FFB00099",
          }}
        />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-semibold tracking-wide"
              style={{ color: active ? "#E5484D" : "#FFB000" }}>
          {active ? "LOCKDOWN ENGAGED" : "SYSTEM ARMED"}
        </span>
        <span className="text-[10px] text-[#7D848D]">
          {active ? "auto breaker: orders purged · flattened" : "7d drawdown breaker monitoring"}
        </span>
      </div>
    </div>
  );
}

function ManualKillSwitch({ paused, onToggle, loading }) {
  return (
    <button
      onClick={onToggle}
      disabled={loading}
      className="flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-semibold tracking-wide transition-colors disabled:opacity-50"
      style={{
        borderColor: paused ? "#E5484D" : "#24282D",
        background: paused ? "#2A1414" : "#101317",
        color: paused ? "#E5484D" : "#7D848D",
        cursor: loading ? "wait" : "pointer"
      }}
    >
      <span className="w-2 h-2 rounded-full"
            style={{ background: paused ? "#E5484D" : "#3FB27F", boxShadow: paused ? "0 0 6px #E5484D" : "0 0 6px #3FB27F" }} />
      {loading ? "COMMUNICATING..." : paused ? "RESUME TRADING" : "PAUSE TRADING"}
    </button>
  );
}

function OrderTicket({ onSubmit, state }) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("BUY");
  const [qty, setQty] = useState("");
  const [orderType, setOrderType] = useState("MARKET");
  const [limitPrice, setLimitPrice] = useState("");

  const isBlocked = state?.lockdown_active || state?.manual_pause;
  const canSubmit = symbol.trim() !== "" && Number(qty) > 0 &&
    (orderType === "MARKET" || Number(limitPrice) > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit?.({ symbol: symbol.toUpperCase(), side, qty: Number(qty), orderType, limitPrice: Number(limitPrice) || null });
    setSymbol(""); setQty(""); setLimitPrice("");
  };

  const inputCls = "bg-[#101317] border border-[#24282D] rounded px-2 py-1.5 text-xs font-mono text-[#E8E6E1] focus:outline-none focus:border-[#FFB000] w-full";

  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "#24282D", background: "#14171A" }}>
      <div className="text-[10px] uppercase tracking-widest text-[#7D848D] mb-3">
        Manual Order Ticket · On-Demand
      </div>
      {isBlocked && (
        <div className="text-xs text-[#E5484D] mb-3 font-mono">
          ⚠ ORDER SUBMISSION BLOCKED BY SAFEGAURDS: {state?.lockdown_active ? "LOCKDOWN ACTIVE" : "MANUAL PAUSE ACTIVE"}
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end">
        <div>
          <label className="text-[10px] text-[#7D848D]">Symbol</label>
          <input className={inputCls} value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="AAPL" />
        </div>
        <div>
          <label className="text-[10px] text-[#7D848D]">Side</label>
          <select className={inputCls} value={side} onChange={(e) => setSide(e.target.value)}>
            <option>BUY</option><option>SELL</option>
          </select>
        </div>
        <div>
          <label className="text-[10px] text-[#7D848D]">Qty</label>
          <input className={inputCls} type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="0" />
        </div>
        <div>
          <label className="text-[10px] text-[#7D848D]">Type</label>
          <select className={inputCls} value={orderType} onChange={(e) => setOrderType(e.target.value)}>
            <option value="MARKET">MARKET</option><option value="LIMIT">LIMIT</option>
          </select>
        </div>
        {orderType === "LIMIT" ? (
          <div>
            <label className="text-[10px] text-[#7D848D]">Limit Px</label>
            <input className={inputCls} type="number" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} placeholder="0.00" />
          </div>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isBlocked}
            className="px-3 py-1.5 rounded text-xs font-semibold tracking-wide disabled:opacity-30"
            style={{ background: side === "BUY" ? "#3FB27F22" : "#E5484D22", color: side === "BUY" ? "#3FB27F" : "#E5484D", border: `1px solid ${side === "BUY" ? "#3FB27F" : "#E5484D"}` }}
          >
            SUBMIT {side}
          </button>
        )}
      </div>
      {orderType === "LIMIT" && (
        <div className="mt-2">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isBlocked}
            className="px-3 py-1.5 rounded text-xs font-semibold tracking-wide disabled:opacity-30"
            style={{ background: side === "BUY" ? "#3FB27F22" : "#E5484D22", color: side === "BUY" ? "#3FB27F" : "#E5484D", border: `1px solid ${side === "BUY" ? "#3FB27F" : "#E5484D"}` }}
          >
            SUBMIT {side}
          </button>
        </div>
      )}
      <div className="text-[10px] text-[#7D848D] mt-2">
        routes through the same Alpaca order path + risk checks as automated trades
      </div>
    </div>
  );
}

// ─── backtest runner ─────────────────────────────────────────────────────────

function BacktestRunner() {
  const [ticker, setTicker] = useState('');
  const [capital, setCapital] = useState(100000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const run = async (e) => {
    e.preventDefault();
    setLoading(true); setResult(null); setError('');
    try {
      const res = await fetch(`${API_BASE}/systematic/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker.toUpperCase(), capital: parseFloat(capital) }),
      });
      const data = await res.json();
      if (data.success) setResult(data);
      else setError(data.error || 'Backtest failed.');
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics || {};
  const retColor = m.total_return_pct > 0 ? "#3FB27F" : "#E5484D";

  return (
    <div className="rounded-lg border p-4 mb-4" style={{ borderColor: "#24282D", background: "#14171A" }}>
      <div className="text-[10px] uppercase tracking-widest text-[#7D848D] mb-3">
        Systematic Backtest Runner (EMA50 / EMA250 / VWAP)
      </div>
      <form onSubmit={run} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end mb-3">
        <div>
          <label className="text-[10px] text-[#7D848D]">Ticker</label>
          <input type="text" placeholder="SPY" value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} required 
                 className="bg-[#101317] border border-[#24282D] rounded px-2 py-1.5 text-xs font-mono text-[#E8E6E1] focus:outline-none focus:border-[#FFB000] w-full" />
        </div>
        <div>
          <label className="text-[10px] text-[#7D848D]">Initial Capital ($)</label>
          <input type="number" min="1000" step="1000" value={capital} onChange={e => setCapital(e.target.value)}
                 className="bg-[#101317] border border-[#24282D] rounded px-2 py-1.5 text-xs font-mono text-[#E8E6E1] focus:outline-none focus:border-[#FFB000] w-full" />
        </div>
        <button type="submit" disabled={loading} 
                className="px-3 py-1.5 rounded text-xs font-semibold tracking-wide"
                style={{ background: "#FFB00022", color: "#FFB000", border: "1px solid #FFB000" }}>
          {loading ? 'Running…' : '▶ Run Backtest'}
        </button>
      </form>

      {error && <div style={{ color: "#E5484D", fontSize: '0.82rem', marginBottom: 10 }}>⚠ {error}</div>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <div className="bg-[#101317] border border-[#24282D] p-2 rounded">
              <div className="text-[9px] text-[#7D848D]">Total Return</div>
              <div className="text-sm font-bold font-mono" style={{ color: retColor }}>{m.total_return_pct}%</div>
            </div>
            <div className="bg-[#101317] border border-[#24282D] p-2 rounded">
              <div className="text-[9px] text-[#7D848D]">Sharpe Ratio</div>
              <div className="text-sm font-bold font-mono">{m.sharpe ?? '—'}</div>
            </div>
            <div className="bg-[#101317] border border-[#24282D] p-2 rounded">
              <div className="text-[9px] text-[#7D848D]">Max Drawdown</div>
              <div className="text-sm font-bold font-mono text-[#E5484D]">{m.max_drawdown_pct}%</div>
            </div>
            <div className="bg-[#101317] border border-[#24282D] p-2 rounded">
              <div className="text-[9px] text-[#7D848D]">Trades</div>
              <div className="text-sm font-bold font-mono">{m.num_trades}</div>
            </div>
            <div className="bg-[#101317] border border-[#24282D] p-2 rounded">
              <div className="text-[9px] text-[#7D848D]">Final Equity</div>
              <div className="text-sm font-bold font-mono text-[#5B8DB8]">${m.final_equity?.toLocaleString()}</div>
            </div>
          </div>
          <details>
            <summary style={{ cursor: 'pointer', fontSize: '0.78rem', color: '#7D848D' }}>Full summary ▸</summary>
            <pre style={{ fontSize: '0.72rem', color: '#7D848D', marginTop: 8, whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace' }}>{result.summary}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- main panel

export default function AlpacaPanel({
  state,
  systematicStatus,
  onRefreshState,
  onRefreshStatus,
  ingestTicker,
  setIngestTicker,
  ingestLoading,
  handleIngestSubmit,
  signalTicker,
  setSignalTicker,
  signalLoading,
  handleGenerateSignal,
  executingLoading,
  handleExecuteSignal,
  fetchSystematicStatus,
}) {
  const [tab, setTab] = useState("positions");
  const [pauseLoading, setPauseLoading] = useState(false);
  const [orderResult, setOrderResult] = useState(null);
  const [orderError, setOrderError] = useState('');

  // Drawdown math from state history
  const { lockdown_active = false, manual_pause = false, equity_history = [] } = state || {};
  
  const equityCurve = useMemo(() => {
    if (!equity_history.length) return [];
    return equity_history.map(item => ({
      date: item.timestamp ? new Date(item.timestamp).toISOString().slice(5, 10) : "",
      equity: Math.round(item.equity)
    }));
  }, [equity_history]);

  const currentEquity = equityCurve.length ? equityCurve[equityCurve.length - 1].equity : 100000;
  const dayPnl = equityCurve.length > 1 ? equityCurve[equityCurve.length - 1].equity - equityCurve[equityCurve.length - 2].equity : 0;
  
  const peak7d = useMemo(() => {
    if (!equityCurve.length) return 100000;
    return Math.max(...equityCurve.slice(-7).map(c => c.equity));
  }, [equityCurve]);

  const drawdown7d = currentEquity > 0 ? ((currentEquity / peak7d) - 1) * 100 : 0;

  const positions = useMemo(() => {
    return systematicStatus?.account?.positions || [];
  }, [systematicStatus]);

  const handleTogglePause = async () => {
    setPauseLoading(true);
    try {
      const newPaused = !state?.manual_pause;
      await fetch(`${API_BASE}/state/manual_pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paused: newPaused }),
      });
      if (onRefreshState) onRefreshState();
    } catch (err) {
      console.error('Failed to toggle manual_pause:', err);
    } finally {
      setPauseLoading(false);
    }
  };

  const handleManualOrderSubmit = async (order) => {
    setOrderResult(null); setOrderError('');
    try {
      const res = await fetch(`${API_BASE}/systematic/manual_order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: order.symbol,
          side: order.side,
          qty: order.qty,
          order_type: order.orderType,
          limit_price: order.limitPrice
        }),
      });
      const data = await res.json();
      if (data.success) {
        setOrderResult(data.order);
        if (onRefreshState) onRefreshState();
      } else {
        setOrderError(data.error || 'Manual order submission failed.');
      }
    } catch (err) {
      setOrderError(String(err));
    }
  };

  return (
    <div className="w-full" style={{ background: "#0B0D0F", color: "#E8E6E1" }}>
      <div className="max-w-6xl mx-auto p-4 md:p-6 font-sans">

        {/* status bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4 mb-4"
             style={{ borderColor: "#24282D", background: "#14171A" }}>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold tracking-[0.2em]" style={{ color: "#FFB000" }}>
              WHITELIGHT
            </span>
            <span className="text-[10px] uppercase tracking-widest text-[#7D848D]">
              🤖 systematic pipeline · live execution
            </span>
          </div>

          <div className="flex items-center gap-8">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#7D848D]">Equity</div>
              <div className="font-mono text-lg tabular-nums">{fmt$(currentEquity)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#7D848D]">Day P&amp;L</div>
              <div className="font-mono text-lg tabular-nums"
                   style={{ color: dayPnl >= 0 ? "#3FB27F" : "#E5484D" }}>
                {dayPnl >= 0 ? "+" : ""}{fmt$(dayPnl)}
              </div>
            </div>
            <BreakerSwitch active={lockdown_active} />
            <div className="w-px h-8" style={{ background: "#24282D" }} />
            <ManualKillSwitch paused={manual_pause} onToggle={handleTogglePause} loading={pauseLoading} />
          </div>
        </div>

        {/* manual order execution alerts */}
        {orderError && (
          <div className="mb-4 p-3 rounded bg-red-950 border border-red-700 text-xs font-mono text-[#E5484D]">
            ⚠ Order Error: {orderError}
          </div>
        )}
        {orderResult && (
          <div className="mb-4 p-3 rounded bg-green-950 border border-green-700 text-xs font-mono text-[#3FB27F]">
            ✅ Order Placed: ID={orderResult.order_id} | Status={orderResult.status}
          </div>
        )}

        {/* manual order entry ticket */}
        <div className="mb-4">
          <OrderTicket onSubmit={handleManualOrderSubmit} state={state} />
        </div>

        {/* Backtester */}
        <BacktestRunner />

        {/* main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-4 mb-4">

          {/* equity curve */}
          <div className="rounded-lg border p-4" style={{ borderColor: "#24282D", background: "#14171A" }}>
            <div className="text-[10px] uppercase tracking-widest text-[#7D848D] mb-2">
              Equity Curve (Rolling 7d history)
            </div>
            {equityCurve.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={equityCurve} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#7D848D" }}
                         axisLine={{ stroke: "#24282D" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#7D848D" }} axisLine={false} tickLine={false}
                         domain={["dataMin - 100", "dataMax + 100"]} />
                  <Tooltip
                    contentStyle={{ background: "#101317", border: "1px solid #24282D", fontSize: 12 }}
                    labelStyle={{ color: "#7D848D" }}
                    formatter={(v) => [fmt$(v), "equity"]}
                  />
                  <Line type="monotone" dataKey="equity" stroke="#FFB000" strokeWidth={1.75} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-56 flex items-center justify-center text-xs text-[#7D848D] font-mono">
                NO PORTFOLIO HISTORY RECORDED YET
              </div>
            )}
          </div>

          {/* risk gauges */}
          <div className="rounded-lg border p-4 flex flex-col" style={{ borderColor: "#24282D", background: "#14171A" }}>
            <div className="text-[10px] uppercase tracking-widest text-[#7D848D] mb-2">
              Risk Instruments
            </div>
            <div className="flex-1 grid grid-cols-3 place-items-center">
              <RadialGauge label="7d Drawdown" value={Math.abs(drawdown7d)} max={15}
                           danger={Math.abs(drawdown7d) >= 15}
                           sub="limit 15%" />
              <RadialGauge label="Margin Heat" value={0} max={100} sub="0% exposure" />
              <RadialGauge label="Net Delta" value={0} max={50}
                           unit="" sub="0.00Δ exposure" />
            </div>
          </div>
        </div>

        {/* tabs: positions / trade log */}
        <div className="rounded-lg border" style={{ borderColor: "#24282D", background: "#14171A" }}>
          <div className="flex border-b" style={{ borderColor: "#24282D" }}>
            {["positions", "trade log"].map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className="px-4 py-2 text-xs uppercase tracking-widest"
                style={{
                  color: tab === t ? "#FFB000" : "#7D848D",
                  borderBottom: tab === t ? "2px solid #FFB000" : "2px solid transparent",
                }}>
                {t}
              </button>
            ))}
          </div>

          {tab === "positions" ? (
            <table className="w-full font-mono text-xs">
              <thead>
                <tr className="text-[#7D848D] border-b" style={{ borderColor: "#24282D" }}>
                  {["Symbol", "Type", "Qty", "Price", "P&L"].map((h) => (
                    <th key={h} className="text-left font-normal px-4 py-2 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.length > 0 ? (
                  positions.map((p, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: "#1B1E22" }}>
                      <td className="px-4 py-2">{p.symbol}</td>
                      <td className="px-4 py-2 text-[#7D848D]">{p.type}</td>
                      <td className="px-4 py-2 tabular-nums">{p.qty}</td>
                      <td className="px-4 py-2 tabular-nums">{p.price}</td>
                      <td className="px-4 py-2 tabular-nums" style={{ color: p.pnl >= 0 ? "#3FB27F" : "#E5484D" }}>
                        {p.pnl >= 0 ? "+" : ""}{fmt$(p.pnl)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-xs text-[#7D848D]">
                      NO ACTIVE POSITIONS IN PORTFOLIO
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <div className="p-4">
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                <button onClick={fetchSystematicStatus} className="px-2 py-1 text-xs font-semibold tracking-wide uppercase border border-[#24282D] rounded text-[#7D848D] hover:text-[#FFB000]">
                  🔄 Refresh Logs
                </button>
              </div>
              <pre className="p-3 bg-[#020617] border border-[#24282D] rounded font-mono text-xs text-[#3FB27F] h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {systematicStatus?.logs || "No logs available."}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
