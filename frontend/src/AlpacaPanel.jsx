import React, { useMemo, useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

/*
  WHITELIGHT — 🤖 ALPACA MIGRATION & SYSTEMATIC PIPELINE
  Modern Dark UI System
*/

const API_BASE = 'http://127.0.0.1:8000/api';

const fmt$ = (n) => (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
const fmtPct = (n, d = 1) => `${n >= 0 ? "+" : ""}${n.toFixed(d)}%`;

function RadialGauge({ label, value, max, unit = "%", danger = false, sub }) {
  const pct = Math.min(Math.abs(value) / max, 1);
  const angle = -140 + pct * 280;
  const color = danger ? "#E5484D" : pct > 0.75 ? "#E5484D" : pct > 0.5 ? "#f59e0b" : "#3FB27F";
  const r = 42, cx = 50, cy = 50;
  const toXY = (deg) => {
    const rad = (deg - 90) * (Math.PI / 180);
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  };
  const [x1, y1] = toXY(-140);
  const [x2, y2] = toXY(140);
  const [nx, ny] = toXY(angle);

  return (
    <div className="flex flex-col items-center gap-1 font-mono">
      <svg viewBox="0 0 100 92" className="w-24 h-24">
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`}
              fill="none" stroke="#1e293b" strokeWidth="6" strokeLinecap="round" />
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${pct > 0.5 ? 1 : 0} 1 ${nx} ${ny}`}
              fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="3" fill={color} />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="2" />
        <text x="50" y="52" textAnchor="middle" fontSize="15" fontFamily="monospace"
              fill="#f8fafc" fontWeight="700">
          {value.toFixed(0)}{unit}
        </text>
      </svg>
      <div className="text-[10px] tracking-widest uppercase text-slate-400 font-bold">{label}</div>
      {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function BreakerSwitch({ active }) {
  return (
    <div className="flex items-center gap-3 font-mono">
      <div className="relative w-14 h-8 rounded-full border border-slate-800 bg-slate-950 p-1 shadow-inner">
        <div
          className="w-6 h-6 rounded-full transition-transform duration-300 shadow-md"
          style={{
            transform: active ? "translateX(24px)" : "translateX(0)",
            background: active
              ? "radial-gradient(circle at 35% 30%, #ff8686, #ef4444)"
              : "radial-gradient(circle at 35% 30%, #fde68a, #f59e0b)",
            boxShadow: active ? "0 0 12px #ef4444" : "0 0 12px #f59e0b",
          }}
        />
      </div>
      <div className="flex flex-col leading-tight">
        <span className={`text-xs font-bold tracking-wide uppercase ${active ? "text-rose-400" : "text-amber-400"}`}>
          {active ? "LOCKDOWN ENGAGED" : "SYSTEM ARMED"}
        </span>
        <span className="text-[10px] text-slate-400">
          {active ? "auto breaker: orders purged" : "7d drawdown breaker active"}
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
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-mono font-bold tracking-wide transition-all ${
        paused
          ? "bg-rose-950/60 border-rose-600/40 text-rose-400"
          : "bg-slate-950 border-slate-800 text-slate-300 hover:border-amber-400"
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${paused ? "bg-rose-500 shadow-rose-500" : "bg-emerald-500 shadow-emerald-500"} shadow-sm`} />
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

  const inputCls = "bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-amber-400 focus:outline-none focus:border-amber-400 w-full";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4 font-mono">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <span className="text-xs uppercase tracking-widest text-amber-400 font-bold">
          Manual Order Ticket · On-Demand Alpaca Execution
        </span>
        {isBlocked && (
          <span className="text-xs text-rose-400 font-bold">
            ⚠ BLOCKED BY SAFEGUARDS ({state?.lockdown_active ? "LOCKDOWN" : "PAUSED"})
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end">
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Symbol</label>
          <input className={inputCls} value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="AAPL" />
        </div>
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Side</label>
          <select className={inputCls} value={side} onChange={(e) => setSide(e.target.value)}>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Quantity</label>
          <input className={inputCls} type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="10" />
        </div>
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Order Type</label>
          <select className={inputCls} value={orderType} onChange={(e) => setOrderType(e.target.value)}>
            <option value="MARKET">MARKET</option>
            <option value="LIMIT">LIMIT</option>
          </select>
        </div>
        {orderType === "LIMIT" ? (
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Limit Px</label>
            <input className={inputCls} type="number" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} placeholder="0.00" />
          </div>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isBlocked}
            className={`w-full py-2 px-4 rounded-lg text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-30 ${
              side === "BUY"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30"
                : "bg-rose-500/20 text-rose-400 border border-rose-500/40 hover:bg-rose-500/30"
            }`}
          >
            Submit {side}
          </button>
        )}
      </div>

      {orderType === "LIMIT" && (
        <div className="pt-2">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isBlocked}
            className={`w-full py-2.5 px-4 rounded-lg text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-30 ${
              side === "BUY"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30"
                : "bg-rose-500/20 text-rose-400 border border-rose-500/40 hover:bg-rose-500/30"
            }`}
          >
            Submit Limit {side}
          </button>
        </div>
      )}
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
  const retColor = m.total_return_pct > 0 ? "#3FB27F" : "#ef4444";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4 font-mono">
      <div className="text-xs uppercase tracking-widest text-amber-400 font-bold border-b border-slate-800 pb-2">
        Systematic Backtest Engine (EMA50 / EMA250 / VWAP)
      </div>

      <form onSubmit={run} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Ticker</label>
          <input
            type="text"
            placeholder="SPY"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            required 
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-amber-400 focus:outline-none focus:border-amber-400 w-full"
          />
        </div>
        <div>
          <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Initial Capital ($)</label>
          <input
            type="number"
            min="1000"
            step="1000"
            value={capital}
            onChange={e => setCapital(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-amber-400 focus:outline-none focus:border-amber-400 w-full"
          />
        </div>
        <button
          type="submit"
          disabled={loading} 
          className="w-full py-2.5 px-4 rounded-lg text-xs font-bold uppercase tracking-wider bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all shadow-lg shadow-amber-500/10"
        >
          {loading ? '⏳ Running...' : '▶ Run Backtest'}
        </button>
      </form>

      {error && <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-700/50 text-xs text-rose-400">⚠ {error}</div>}

      {result && (
        <div className="space-y-3 pt-2">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
            <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl space-y-1">
              <div className="text-[10px] text-slate-400 uppercase">Total Return</div>
              <div className="text-base font-bold" style={{ color: retColor }}>{m.total_return_pct}%</div>
            </div>
            <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl space-y-1">
              <div className="text-[10px] text-slate-400 uppercase">Sharpe Ratio</div>
              <div className="text-base font-bold text-white">{m.sharpe ?? '—'}</div>
            </div>
            <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl space-y-1">
              <div className="text-[10px] text-slate-400 uppercase">Max Drawdown</div>
              <div className="text-base font-bold text-rose-400">{m.max_drawdown_pct}%</div>
            </div>
            <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl space-y-1">
              <div className="text-[10px] text-slate-400 uppercase font-bold">Trades</div>
              <div className="text-base font-bold text-white">{m.num_trades}</div>
            </div>
            <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl space-y-1">
              <div className="text-[10px] text-slate-400 uppercase font-bold">Final Equity</div>
              <div className="text-base font-bold text-amber-400">${m.final_equity?.toLocaleString()}</div>
            </div>
          </div>
          <details>
            <summary className="cursor-pointer text-xs text-slate-400 hover:text-amber-400 font-mono">Full Backtest Summary ▸</summary>
            <pre className="mt-2 p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 font-mono whitespace-pre-wrap">{result.summary}</pre>
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

  const currentEquity = equityCurve.length ? equityCurve[equityCurve.length - 1].equity : 100054.24;
  const dayPnl = equityCurve.length > 1 ? equityCurve[equityCurve.length - 1].equity - equityCurve[equityCurve.length - 2].equity : 54.24;
  
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
    <div className="p-4 space-y-6 text-slate-100 font-sans" style={{ background: "#0b0e11", minHeight: "100vh" }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Top Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="text-xl">⚡</span>
            <h1 className="text-lg font-bold tracking-tight text-amber-400 font-mono">Alpaca Systematic Engine</h1>
            <span className="px-2.5 py-0.5 text-xs font-mono rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ● Live Execution Armed
            </span>
          </div>

          <div className="flex items-center gap-6">
            <BreakerSwitch active={lockdown_active} />
            <div className="w-px h-8 bg-slate-800" />
            <ManualKillSwitch paused={manual_pause} onToggle={handleTogglePause} loading={pauseLoading} />
          </div>
        </div>

        {/* Top KPI Cards (Matching Options Trading Tab Style) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">💳 Portfolio Equity</span>
            <div className="text-xl font-black text-amber-400">
              {fmt$(currentEquity)}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">📈 Day P&amp;L</span>
            <div className={`text-xl font-black ${dayPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {dayPnl >= 0 ? "+" : ""}{fmt$(dayPnl)}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">🛡️ 7D Max Drawdown</span>
            <div className="text-xl font-black text-emerald-400">
              {Math.abs(drawdown7d).toFixed(1)}% <span className="text-xs text-slate-500 font-normal">/ 15.0% Limit</span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">⚡ Active Positions</span>
            <div className="text-xl font-black text-white">
              {positions.length} Active
            </div>
          </div>
        </div>

        {/* Manual Order Execution Alerts */}
        {orderError && (
          <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-700/50 text-xs font-mono text-rose-400">
            ⚠ Order Error: {orderError}
          </div>
        )}
        {orderResult && (
          <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-700/50 text-xs font-mono text-emerald-400">
            ✅ Order Placed: ID={orderResult.order_id} | Status={orderResult.status}
          </div>
        )}

        {/* Manual Order Entry Ticket */}
        <OrderTicket onSubmit={handleManualOrderSubmit} state={state} />

        {/* Backtester */}
        <BacktestRunner />

        {/* Main Grid: Equity Curve & Risk Gauges */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Equity Curve */}
          <div className="lg:col-span-8 rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3 font-mono">
            <div className="text-xs uppercase tracking-widest text-slate-400 font-bold border-b border-slate-800 pb-2">
              Equity Curve (Rolling 7d History)
            </div>
            {equityCurve.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={equityCurve} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }}
                         axisLine={{ stroke: "#1e293b" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}
                         domain={["dataMin - 100", "dataMax + 100"]} />
                  <Tooltip
                    contentStyle={{ background: "#090d16", border: "1px solid #1e293b", fontSize: 12 }}
                    labelStyle={{ color: "#94a3b8" }}
                    formatter={(v) => [fmt$(v), "equity"]}
                  />
                  <Line type="monotone" dataKey="equity" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-56 flex items-center justify-center text-xs text-slate-500 font-mono">
                NO PORTFOLIO HISTORY RECORDED YET
              </div>
            )}
          </div>

          {/* Risk Instruments */}
          <div className="lg:col-span-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 flex flex-col font-mono">
            <div className="text-xs uppercase tracking-widest text-slate-400 font-bold border-b border-slate-800 pb-2 mb-4">
              Risk Instruments & Gauges
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

        {/* Tabs: Positions / Trade Log Table */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden font-mono text-xs">
          <div className="flex border-b border-slate-800 bg-slate-950/40">
            {["positions", "trade log"].map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-5 py-3 text-xs uppercase tracking-widest font-bold transition-all border-b-2 ${
                  tab === t
                    ? "border-amber-400 text-amber-400 bg-amber-400/5"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === "positions" ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Quantity</th>
                    <th className="py-3 px-4">Price</th>
                    <th className="py-3 px-4">Unrealized P&amp;L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {positions.length > 0 ? (
                    positions.map((p, i) => (
                      <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4 font-bold text-amber-400">{p.symbol}</td>
                        <td className="py-3 px-4 text-slate-300 uppercase">{p.type}</td>
                        <td className="py-3 px-4 text-white font-bold">{p.qty}</td>
                        <td className="py-3 px-4 text-slate-200">${p.price}</td>
                        <td className={`py-3 px-4 font-bold ${p.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {p.pnl >= 0 ? "+" : ""}{fmt$(p.pnl)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-xs text-slate-500 font-mono">
                        NO ACTIVE POSITIONS IN PORTFOLIO
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-5 space-y-3">
              <div className="flex justify-end">
                <button
                  onClick={fetchSystematicStatus}
                  className="px-3 py-1.5 text-xs font-bold uppercase tracking-wider rounded-lg border border-slate-700 bg-slate-900 text-slate-300 hover:text-amber-400 hover:border-amber-400 transition-colors"
                >
                  🔄 Refresh Logs
                </button>
              </div>
              <pre className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-emerald-400 h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {systematicStatus?.logs || "No execution logs available."}
              </pre>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
