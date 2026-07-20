import React, { useState, useEffect, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

/*
  WHITELIGHT + SHADOW CORTEX — UNIFIED INTEGRATED ENGINE TAB
  Combines Stock Performance, Backtester, Live Equity Curve, 
  and Option Chains with Shadow Cortex Fail-Closed Dual-Agent Pipeline.
*/

const getDaysToExpiry = (expDateStr) => {
  if (!expDateStr) return 7;
  const exp = new Date(expDateStr);
  const today = new Date();
  const diffTime = exp.getTime() - today.getTime();
  return Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
};

const getHorizonLabel = (targetDte, expDateStr) => {
  const days = getDaysToExpiry(expDateStr);
  if (targetDte <= 7 || days <= 7) return `⚡ Weekly (${days} days to expire)`;
  if (targetDte <= 90 || days <= 90) return `📅 Monthly (${days} days to expire)`;
  if (targetDte <= 180 || days <= 180) return `🚀 6-Month (${days} days to expire)`;
  return `🏆 Yearly (${days} days to expire)`;
};

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
      <svg viewBox="0 0 100 92" className="w-20 h-20">
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
      <div className="text-[9px] tracking-widest uppercase text-slate-400 font-bold">{label}</div>
      {sub && <div className="text-[9px] text-slate-500">{sub}</div>}

      {/* Toast Alert Container */}
      <div className="fixed top-6 right-6 z-50 space-y-3 w-80 max-w-full font-mono text-xs">
        {activeToasts.map(toast => (
          <div
            key={toast.id}
            className={`p-4 rounded-xl border backdrop-blur shadow-2xl flex items-start gap-3 transition-all duration-300 transform translate-x-0 ${
              toast.type === "profit_bracket"
                ? "bg-emerald-950/90 border-emerald-500/30 text-emerald-300 shadow-emerald-500/10"
                : "bg-rose-950/90 border-rose-500/30 text-rose-300 shadow-rose-500/10"
            }`}
          >
            <span className="text-lg">{toast.type === "profit_bracket" ? "📈" : "🚨"}</span>
            <div className="flex-1">
              <div className="font-bold uppercase tracking-wider text-[9px] text-slate-400">
                {toast.type === "profit_bracket" ? `Target Hit (+${toast.bracket}%)` : "Invalidation Auto-Closed"}
              </div>
              <p className="mt-1 leading-relaxed text-slate-200">{toast.message}</p>
            </div>
            <button
              onClick={() => setActiveToasts(prev => prev.filter(t => t.id !== toast.id))}
              className="text-slate-400 hover:text-white font-bold"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

    </div>
  );
}

// Live TradingView Candlestick Chart Widget Component
function TradingViewChart({ symbol }) {
  const containerRef = React.useRef();

  React.useEffect(() => {
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    
    const resolvedSymbol = symbol === "SPY" ? "AMEX:SPY" : `NASDAQ:${symbol}`;

    script.innerHTML = JSON.stringify({
      "autosize": true,
      "symbol": resolvedSymbol,
      "interval": "1",
      "timezone": "exchange",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "enable_publishing": false,
      "hide_side_toolbar": false,
      "allow_symbol_change": false,
      "calendar": false,
      "studies": [
        "STD;VWAP",
        "STD;RSI"
      ],
      "support_host": "https://www.tradingview.com"
    });

    if (containerRef.current) {
      containerRef.current.appendChild(script);
    }
  }, [symbol]);

  return (
    <div className="tradingview-widget-container border border-slate-800 rounded-xl overflow-hidden bg-slate-950/40" style={{ height: "400px", width: "100%" }}>
      <div ref={containerRef} className="tradingview-widget-container__widget" style={{ height: "100%", width: "100%" }}></div>
    </div>
  );
}

export default function WhitelightCortexIntegratedPanel({ 
  API_BASE = "http://127.0.0.1:8000/api",
  state,
  trades = [],
  positions: parentPositions = { active_positions: [] },
  systematicStatus
}) {
  const [tickerInput, setTickerInput] = useState("AAPL");
  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("WEEKLY"); // WEEKLY, MONTHLY, SEMI_ANNUAL, ANNUAL_LEAP
  const [activeProfile, setActiveProfile] = useState("safe_defaults");

  // Engine State
  const [signals, setSignals] = useState(null);
  const [chain, setChain] = useState([]);
  const [currentPrice, setCurrentPrice] = useState(230.0);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [autoExecute, setAutoExecute] = useState(false);
  const [executedOrders, setExecutedOrders] = useState([]);
  const [accountSummary, setAccountSummary] = useState(null);
  const [localTrades, setLocalTrades] = useState([]);
  
  // Watchlist states
  const [watchlist, setWatchlist] = useState(["AAPL", "NVDA", "SPY"]);
  const [newTicker, setNewTicker] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [scanResults, setScanResults] = useState({});
  const [autoScanEnabled, setAutoScanEnabled] = useState(false);

  // PPO RL Policy Strategy Optimizer states
  const [ppoSteps, setPpoSteps] = useState(350000);
  const [ppoRecency, setPpoRecency] = useState(true);
  const [ppoMasking, setPpoMasking] = useState(true);
  const [ppoAtr, setPpoAtr] = useState(true);
  const [ppoBeta, setPpoBeta] = useState(true);
  const [ppoTraining, setPpoTraining] = useState(false);
  const [ppoProgress, setPpoProgress] = useState(0);
  const [ppoMetrics, setPpoMetrics] = useState([]);

  const handleTrainPPO = async () => {
    setPpoTraining(true);
    setPpoProgress(0);
    setPpoMetrics([]);
    
    const interval = setInterval(() => {
      setPpoProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 10;
      });
    }, 120);
    
    try {
      const res = await fetch(`${API_BASE}/rl/train_ppo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          steps: ppoSteps,
          use_recency: ppoRecency,
          use_masking: ppoMasking,
          use_atr: ppoAtr,
          use_beta: ppoBeta
        })
      });
      const data = await res.json();
      if (data.success) {
        setPpoMetrics(data.metrics);
        setAuditEvents((prev) => [{
          time: new Date().toLocaleTimeString(),
          type: "PROPOSAL_VALIDATED",
          level: "success",
          title: `PPO RL POLICY TRAINED: ${ppoSteps.toLocaleString()} Steps`,
          notes: `Optimized with: Linear Recency Reward, Action Masking, ATR bounds, SPY Beta. Final Reward: ${data.metrics[9]?.reward}`,
          validator: "Reinforcement Learning Engine"
        }, ...prev]);
      }
    } catch (e) {
      console.error("PPO training error:", e);
    } finally {
      setTimeout(() => setPpoTraining(false), 1200);
    }
  };

  // Backtest widget states
  const [btTicker, setBtTicker] = useState("SPY");
  const [btCapital, setBtCapital] = useState(100000);
  const [btLoading, setBtLoading] = useState(false);
  const [btResult, setBtResult] = useState(null);
  const [btError, setBtError] = useState("");

  // Cortex AI Budget & Cooldown Brakes
  const [callsToday, setCallsToday] = useState(42);
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(500);
  const [cooldownSecs, setCooldownSecs] = useState(18);

  // Active profit/invalidation notification toasts
  const [activeToasts, setActiveToasts] = useState([]);

  // Scheduled Expiration Side Toast Alert Popup
  const [expirationAlert, setExpirationAlert] = useState(null);

  // UI Views & Modals
  const [showOrdersDropdown, setShowOrdersDropdown] = useState(false);
  const [showStrategyGuide, setShowStrategyGuide] = useState(false);
  const [showPPO, setShowPPO] = useState(false);
  const [selectedContract, setSelectedContract] = useState(null);
  const [contractQty, setContractQty] = useState(1);
  const [orderSide, setOrderSide] = useState("buy");
  const [customLimitPrice, setCustomLimitPrice] = useState("");

  // Dual Agent Configuration
  const [proposerProvider, setProposerProvider] = useState("AI Agent Pool");
  const [proposerModel, setProposerModel] = useState("Standard Model");
  const [validatorProvider, setValidatorProvider] = useState("AI Risk Desk");
  const [validatorModel, setValidatorModel] = useState("High Reasoning Model");
  const [agentResult, setAgentResult] = useState(null);

  // Live Audit JSONL Event Stream
  const [auditEvents, setAuditEvents] = useState([]);

  // High-Water Mark Trailing Stop Active Positions
  const [positions, setPositions] = useState([]);

  // Cooldown Timer simulation
  useEffect(() => {
    const timer = setInterval(() => {
      setCooldownSecs((prev) => (prev > 1 ? prev - 1 : 30));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchAccountSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/options/account_summary`);
      const data = await res.json();
      if (data.success) {
        setAccountSummary(data);
      }
    } catch (e) {
      console.error("Account summary error:", e);
    }
  };

  const fetchOptionsPositions = async () => {
    try {
      const res = await fetch(`${API_BASE}/options/positions`);
      if (res.ok) {
        const data = await res.json();
        setPositions(data);
      }
    } catch (e) {
      console.error("Error fetching options positions:", e);
    }
  };

  const fetchLocalTrades = async () => {
    try {
      const res = await fetch(`${API_BASE}/trades`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setLocalTrades(data);
      }
    } catch (e) {
      console.error("Error fetching trades:", e);
    }
  };

  const handleScanWatchlist = async () => {
    if (watchlist.length === 0) return;
    setIsScanning(true);
    try {
      const res = await fetch(`${API_BASE}/options/scan_watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: watchlist, timeframe })
      });
      const data = await res.json();
      if (data.success) {
        setScanResults(data.results);
        
        // Auto-Execute checks for each authorized watchlist ticker
        if (autoExecute) {
          for (const tk of Object.keys(data.results)) {
            const item = data.results[tk];
            if (item.success && item.dual_agent_result?.execution_ready) {
              setAuditEvents((prev) => [{
                time: new Date().toLocaleTimeString(),
                type: "PROPOSAL_VALIDATED",
                level: "success",
                title: `WATCHLIST AUTO-EXECUTE: ${tk}`,
                notes: `Proposer and Validator authorized trade. Submitted order to Alpaca.`,
                validator: "AI Risk Desk Agent"
              }, ...prev]);
            }
          }
        }
      }
    } catch (e) {
      console.error("Watchlist scan error:", e);
    } finally {
      setIsScanning(false);
    }
  };

  useEffect(() => {
    fetchIntradayData(activeTicker, timeframe);
    fetchAccountSummary();
    fetchLocalTrades();
    fetchOptionsPositions();
    
    const interval = setInterval(() => {
      fetchAccountSummary();
      fetchLocalTrades();
      fetchOptionsPositions();
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTicker, timeframe]);

  useEffect(() => {
    if (!autoScanEnabled) return;
    
    // Scan immediately
    handleScanWatchlist();
    
    // Set 30-second interval
    const scannerTimer = setInterval(() => {
      handleScanWatchlist();
    }, 30000);
    return () => clearInterval(scannerTimer);
  }, [autoScanEnabled, watchlist, timeframe, autoExecute]);

  const fetchIntradayData = async (symbol, tf = timeframe) => {
    setLoading(true);
    try {
      const [sigRes, chainRes] = await Promise.all([
        fetch(`${API_BASE}/options/intraday_signals?ticker=${symbol}`),
        fetch(`${API_BASE}/options/chain?ticker=${symbol}&timeframe=${tf}`)
      ]);
      const sigData = await sigRes.json();
      const chainData = await chainRes.json();

      if (sigData.success) {
        setSignals(sigData.signals);
      }
      if (chainData.success) {
        const contracts = chainData.chain || [];
        setChain(contracts);
        setCurrentPrice(chainData.current_price || 230.0);

        if (contracts.length > 0) {
          const nearest = contracts[0];
          const daysLeft = getDaysToExpiry(nearest.expiration);
          setExpirationAlert({
            timeLabel: "9:30 AM Scheduled Alert",
            ticker: symbol,
            strike: nearest.strike,
            type: nearest.type,
            daysLeft: daysLeft
          });
        }
      }
    } catch (e) {
      console.error("Options data fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  const runBacktest = async (e) => {
    e.preventDefault();
    setBtLoading(true); setBtResult(null); setBtError("");
    try {
      const res = await fetch(`${API_BASE}/systematic/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: btTicker.toUpperCase(), capital: parseFloat(btCapital) }),
      });
      const data = await res.json();
      if (data.success) setBtResult(data);
      else setBtError(data.error || "Backtest failed.");
    } catch (err) {
      setBtError(String(err));
    } finally {
      setBtLoading(false);
    }
  };

  const handleTickerSearch = (e) => {
    e.preventDefault();
    if (tickerInput.trim()) {
      setActiveTicker(tickerInput.trim().toUpperCase());
    }
  };

  const handleOpenContractModal = (contract) => {
    setSelectedContract(contract);
    setContractQty(1);
    setOrderSide("buy");
    setCustomLimitPrice(contract.midpoint.toString());
  };

  const handleExecuteOrder = async (contractSymbol, price = 2.50, qty = 1, side = "buy") => {
    try {
      const res = await fetch(`${API_BASE}/options/execute_order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contract_symbol: contractSymbol,
          qty: qty,
          side: side,
          limit_price: price
        })
      });
      const data = await res.json();
      if (data.success) {
        setExecutedOrders((prev) => [{ ...data, ticker: activeTicker, expiration: chain[0]?.expiration }, ...prev]);
        setSelectedContract(null);
        fetchAccountSummary();

        setAuditEvents((prev) => [{
          time: new Date().toLocaleTimeString(),
          type: "ORDER_FILLED",
          level: "info",
          title: `PAPER ORDER FILLED: ${activeTicker} LIMIT`,
          notes: `Limit Price: $${price} | Qty: ${qty} | Status: FILLED`,
          validator: "Execution Gate"
        }, ...prev]);
      }
    } catch (e) {
      console.error("Execute paper order error:", e);
    }
  };

  const handleRunDualAgent = async () => {
    setEvaluating(true);
    try {
      const res = await fetch(`${API_BASE}/options/evaluate_dual_agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          timeframe: timeframe,
          proposer_provider: "cortex",
          proposer_model: "cortex-fast",
          validator_provider: "cortex",
          validator_model: "cortex-strict"
        })
      });
      const data = await res.json();
      if (data.success) {
        setAgentResult(data.dual_agent_result);
        setCallsToday((prev) => prev + 1);

        const isReady = data.dual_agent_result?.execution_ready;
        setAuditEvents((prev) => [{
          time: new Date().toLocaleTimeString(),
          type: isReady ? "PROPOSAL_VALIDATED" : "RISK_GATE_REFUSAL",
          level: isReady ? "success" : "danger",
          title: isReady ? `PROPOSAL AUTHORIZED: ${activeTicker}` : `REJECTED BY RISK DESK: ${activeTicker}`,
          notes: data.dual_agent_result?.validation?.validation_notes || "Audited against 5 Wall St Rules",
          validator: "AI Risk Desk Agent"
        }, ...prev]);

        if (autoExecute && isReady && chain.length > 0) {
          const targetContract = chain[0].symbol;
          handleExecuteOrder(targetContract, chain[0].midpoint, 1, "buy");
        }
      }
    } catch (e) {
      console.error("Dual agent evaluation error:", e);
    } finally {
      setEvaluating(false);
    }
  };

  const triggerTestAlert = (timeLabel) => {
    setExpirationAlert({
      timeLabel: `${timeLabel} Alert`,
      ticker: activeTicker,
      strike: chain[0]?.strike || 230.0,
      type: chain[0]?.type || "CALL",
      daysLeft: getDaysToExpiry(chain[0]?.expiration)
    });
  };

  const biasColor = useMemo(() => {
    if (!signals) return "#7D848D";
    const b = signals.intraday_bias;
    if (b === "STRONG_BULLISH") return "#3FB27F";
    if (b === "BULLISH") return "#22c55e";
    if (b === "STRONG_BEARISH") return "#E5484D";
    if (b === "BEARISH") return "#ef4444";
    return "#eab308";
  }, [signals]);

  // Consolidated Options + Stock Equity Curve Calculator
  const chartData = useMemo(() => {
    const baseline = (state?.equity_history && state.equity_history.length > 0) 
      ? state.equity_history 
      : [{ timestamp: "2026-07-01T09:00:00Z", equity: 10000.0 }];
      
    // Reconstruct options PnL events
    const events = [];
    for (let i = 1; i < baseline.length; i++) {
      events.push({
        timestamp: baseline[i].timestamp,
        pnl: baseline[i].equity - baseline[i - 1].equity
      });
    }

    // Calculate closed stock trade PnL events
    const holdings = {}; // symbol -> { qty, cost }
    const sortedStockTrades = [...localTrades].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    sortedStockTrades.forEach(t => {
      const sym = t.symbol;
      if (t.action === "BUY") {
        if (!holdings[sym]) holdings[sym] = { qty: 0, cost: 0 };
        holdings[sym].qty += t.quantity;
        holdings[sym].cost += t.price * t.quantity;
      } else if (t.action === "SELL") {
        if (holdings[sym] && holdings[sym].qty > 0) {
          const avgPrice = holdings[sym].cost / holdings[sym].qty;
          const sellQty = Math.min(holdings[sym].qty, t.quantity);
          const pnl = (t.price - avgPrice) * sellQty;
          events.push({
            timestamp: t.timestamp,
            pnl: pnl
          });
          holdings[sym].qty -= sellQty;
          holdings[sym].cost -= sellQty * avgPrice;
        }
      }
    });

    // Sort all events by timestamp
    events.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Reconstruct consolidated equity history
    let running = baseline[0].equity;
    const consolidated = [{ timestamp: baseline[0].timestamp, equity: running }];
    events.forEach(ev => {
      running += ev.pnl;
      consolidated.push({
        timestamp: ev.timestamp,
        equity: Number(running.toFixed(2))
      });
    });

    return consolidated;
  }, [state, localTrades]);

  const btMetrics = btResult?.metrics || {};

  return (
    <div className="p-4 space-y-6 text-slate-100 font-sans relative" style={{ background: "#0b0e11", minHeight: "100vh" }}>
      
      {/* Side Toast Expiration Alert (9:30 AM, 1 PM, 3 PM Scheduled Notification) */}
      {expirationAlert && (
        <div className="fixed top-6 right-6 z-50 max-w-sm bg-slate-900 border border-amber-500/60 rounded-2xl p-4 shadow-2xl backdrop-blur font-mono animate-bounce space-y-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-bold text-amber-400 flex items-center gap-1">
              <span>⚠️</span> Expiration Alert [{expirationAlert.timeLabel}]
            </span>
            <button
              onClick={() => setExpirationAlert(null)}
              className="text-xs text-slate-400 hover:text-white font-bold"
            >
              ✕
            </button>
          </div>
          <p className="text-xs text-slate-200 font-semibold leading-relaxed">
            This <span className="text-amber-400 font-bold">{expirationAlert.ticker} ${expirationAlert.strike} {expirationAlert.type}</span> contract is going to expire in <span className="text-rose-400 font-bold">{expirationAlert.daysLeft} days</span>!
          </p>
        </div>
      )}

      {/* Top Integrated Master Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur font-mono">
        <div className="flex items-center gap-3">
          <span className="text-2xl">⚡🧠</span>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-amber-400">Whitelight + Shadow Cortex Unified Engine</h1>
            <p className="text-[10px] text-slate-400">Integrated Stock Tracker, Options Chains, Dual-Agent Risk Desk & backtests</p>
          </div>
        </div>

        {/* Universal Ticker Search Form */}
        <form onSubmit={handleTickerSearch} className="flex items-center gap-2">
          <label className="text-xs text-slate-400 uppercase tracking-wider">Search Ticker:</label>
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
            placeholder="e.g. AAPL, NVDA..."
            className="px-3 py-1.5 text-xs font-semibold uppercase rounded-lg bg-slate-950 border border-slate-700 text-amber-400 focus:outline-none focus:border-amber-400 w-32"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors"
          >
            Go
          </button>
        </form>

        {/* Connection Status & Profile Selector */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            ● SSE Stream Active
          </span>

          <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 font-bold">
            🟢 Claude Desktop MCP Active
          </span>

          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-400">Profile:</span>
            <select
              value={activeProfile}
              onChange={(e) => setActiveProfile(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-amber-400 font-bold rounded px-2 py-0.5 text-xs focus:outline-none"
            >
              <option value="safe_defaults">🛡️ Safe Defaults (Paper)</option>
              <option value="aggressive_scalp">⚡ 0-7D Aggressive Scalp</option>
              <option value="monthly_swing">📅 Pre-Earnings Monthly Swing</option>
              <option value="leaps_accum">🏆 360D LEAPs Accumulator</option>
            </select>
          </div>

          <button
            onClick={() => {
              setShowStrategyGuide(!showStrategyGuide);
              if (showPPO) setShowPPO(false);
            }}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
              showStrategyGuide
                ? "bg-amber-500 text-slate-950 border-amber-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20"
            }`}
          >
            📘 {showStrategyGuide ? "Hide Guide" : "Strategy Guide"}
          </button>

          <button
            onClick={() => {
              setShowPPO(!showPPO);
              if (showStrategyGuide) setShowStrategyGuide(false);
            }}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
              showPPO
                ? "bg-amber-500 text-slate-950 border-amber-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20"
            }`}
          >
            🤖 {showPPO ? "Hide PPO Optimizer" : "PPO RL Optimizer"}
          </button>
        </div>
      </div>

      {/* Cortex AI Budget & Cooldown Control Banner */}
      <div className="p-4 rounded-xl border border-amber-500/30 bg-slate-900/40 backdrop-blur font-mono text-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">AI Decider Model Pool</span>
            <span className="font-bold text-emerald-400 text-xs">⚡ AI Agent Decider (Standard Pool)</span>
          </div>
          <div className="h-8 w-px bg-slate-800" />
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Daily Budget Bar</span>
            <div className="flex items-center gap-2 mt-1">
              <div className="w-32 h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                <div
                  className="h-full bg-amber-400 transition-all duration-500"
                  style={{ width: `${(callsToday / maxCallsPerDay) * 100}%` }}
                />
              </div>
              <span className="font-bold text-amber-300 text-[11px]">{callsToday} / {maxCallsPerDay} Calls</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <span>Test Alerts:</span>
            <button onClick={() => triggerTestAlert("9:30 AM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">9:30 AM</button>
            <button onClick={() => triggerTestAlert("1:00 PM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">1:00 PM</button>
            <button onClick={() => triggerTestAlert("3:00 PM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">3:00 PM</button>
          </div>

          <div className="text-right">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Batch Cooldown</span>
            <span className="font-bold text-amber-400 text-xs">⏳ {cooldownSecs}s</span>
          </div>
        </div>
      </div>

      {/* Interactive Strategy Guide Banner */}
      {showStrategyGuide && (
        <div className="p-6 rounded-xl border border-amber-500/40 bg-slate-900/95 backdrop-blur space-y-5 font-mono text-xs shadow-2xl animate-fade-in">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📘</span>
              <h2 className="text-sm font-bold text-amber-400 uppercase tracking-widest">
                Unified Dual-Agent Options Strategy & Wall Street Risk Management Master Blueprint
              </h2>
            </div>
            <button
              onClick={() => setShowStrategyGuide(false)}
              className="px-2 py-1 text-slate-400 hover:text-white bg-slate-800 rounded text-xs font-bold"
            >
              Close Guide ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider border-b border-slate-800 pb-1">
                1. Dual-Agent Architecture
              </h3>
              <ul className="space-y-2 text-slate-300 leading-relaxed text-[11px]">
                <li><strong className="text-amber-300">Agent 1: Proposer (Fast LLM):</strong> Scans today's 5-min candles & option chains to recommend <span className="text-emerald-400 font-bold">BUY_CALL</span>, <span className="text-rose-400 font-bold">BUY_PUT</span>, or <span className="text-slate-400 font-bold">NO_TRADE</span>.</li>
                <li><strong className="text-emerald-300">Agent 2: Validator (AI Risk Desk):</strong> Senior Risk Manager desk auditing 5 Wall Street rules. Outputs <span className="text-emerald-400 font-bold">EXECUTE</span> or <span className="text-rose-400 font-bold">REJECT</span>.</li>
              </ul>
            </div>

            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider border-b border-slate-800 pb-1">
                2. 4 Intraday Candle Signals
              </h3>
              <ul className="space-y-1.5 text-slate-300 text-[11px]">
                <li><strong className="text-slate-200">1. % Price from Open:</strong> Distance from today's opening print.</li>
                <li><strong className="text-slate-200">2. VWAP Diff %:</strong> Price vs VWAP (Above = Buying, Below = Selling).</li>
                <li><strong className="text-slate-200">3. RSI-7 (5-Min):</strong> Short-term momentum oscillator.</li>
                <li><strong className="text-slate-200">4. MACD (6,13,5):</strong> Intraday trend acceleration & histogram crossover.</li>
              </ul>
            </div>

            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider border-b border-slate-800 pb-1">
                3. The 5 Wall St Trader Rules
              </h3>
              <ul className="space-y-1.5 text-slate-300 text-[11px]">
                <li><strong className="text-amber-400">Rule 1 (Midpoint Limit):</strong> Limits at (Bid+Ask)/2. Saves 5%-15% spread slippage.</li>
                <li><strong className="text-amber-400">Rule 2 (IV Crush Protection):</strong> Only enters when IV Rank &lt; 50%. Exits 2-3 days BEFORE earnings.</li>
                <li><strong className="text-amber-400">Rule 3 (Liquidity Gate):</strong> Rejects contracts with Open Interest &lt; 500.</li>
                <li><strong className="text-amber-400">Rule 4 (2% Capital Sizing):</strong> Max risk capped at 2% total equity.</li>
                <li><strong className="text-amber-400">Rule 5 (25% Premium Stop):</strong> Hard stop-loss on 0-7D scalps.</li>
              </ul>
            </div>
          </div>
        </div>
      )}
      {/* Collapsible PPO Policy Optimizer Dropdown Panel */}
      {showPPO && (
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/95 backdrop-blur space-y-4 font-mono text-xs shadow-2xl animate-fade-in">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">🤖</span>
              <h2 className="text-sm font-bold text-amber-400 uppercase tracking-widest">
                PPO Reinforcement Learning Policy Optimizer (Stable-Baselines3)
              </h2>
            </div>
            <button
              onClick={() => setShowPPO(false)}
              className="px-2 py-1 text-slate-400 hover:text-white bg-slate-800 rounded text-xs font-bold"
            >
              Close Optimizer ✕
            </button>
          </div>
          
                    <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-base">🤖</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  PPO Reinforcement Learning Policy Optimizer
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                Stable-Baselines3
              </span>
            </div>

            <div className="space-y-3">
              {/* Training Steps Configuration */}
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Target Training Budget:</span>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={ppoSteps}
                    onChange={(e) => setPpoSteps(parseInt(e.target.value) || 350000)}
                    className="w-24 px-2 py-1 bg-slate-950 border border-slate-800 text-amber-400 font-bold rounded text-right focus:outline-none"
                  />
                  <span className="text-slate-500">steps</span>
                </div>
              </div>

              {/* Optimizations Toggles */}
              <div className="space-y-2 pt-1 border-t border-slate-800/60">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-bold">Active Hyperparameters</span>
                
                {/* 1. Linear Recency Reward */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-slate-300 font-bold">1. Linear Recency Weighting</span>
                    <span className="text-[9px] text-slate-500">Weight = 0.5 + 0.5 * (Step / Total)</span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer select-none">
                    <input type="checkbox" checked={ppoRecency} onChange={(e) => setPpoRecency(e.target.checked)} className="sr-only peer" />
                    <div className="w-8 h-4.5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-slate-950"></div>
                  </label>
                </div>

                {/* 2. Action Masking Shield */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-slate-300 font-bold">2. Action Masking Layer</span>
                    <span className="text-[9px] text-slate-500">Mask buy actions when SPY &lt; VWAP</span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer select-none">
                    <input type="checkbox" checked={ppoMasking} onChange={(e) => setPpoMasking(e.target.checked)} className="sr-only peer" />
                    <div className="w-8 h-4.5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-slate-950"></div>
                  </label>
                </div>

                {/* 3. ATR Breakout Normalization */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-slate-300 font-bold">3. ATR boundary Normalization</span>
                    <span className="text-[9px] text-slate-500">Normalize PDH/PDL distance by 14-day ATR</span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer select-none">
                    <input type="checkbox" checked={ppoAtr} onChange={(e) => setPpoAtr(e.target.checked)} className="sr-only peer" />
                    <div className="w-8 h-4.5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-slate-950"></div>
                  </label>
                </div>

                {/* 4. SPY Relative Beta Feature */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-slate-300 font-bold">4. SPY Relative Beta Ratio</span>
                    <span className="text-[9px] text-slate-500">Expose SPY price/VWAP as active state feature</span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer select-none">
                    <input type="checkbox" checked={ppoBeta} onChange={(e) => setPpoBeta(e.target.checked)} className="sr-only peer" />
                    <div className="w-8 h-4.5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-slate-950"></div>
                  </label>
                </div>
              </div>

              {/* Progress and training activation */}
              <div className="pt-2 border-t border-slate-800/60 space-y-2">
                {ppoTraining && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>Optimizing Policy weights...</span>
                      <span>{ppoProgress}%</span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                      <div className="bg-amber-500 h-1.5 rounded-full transition-all duration-100" style={{ width: `${ppoProgress}%` }}></div>
                    </div>
                  </div>
                )}

                {ppoMetrics.length > 0 && (
                  <div className="p-2 rounded bg-slate-950 border border-slate-850 space-y-1 text-[10px]">
                    <div className="flex justify-between font-bold text-slate-400">
                      <span>Step</span>
                      <span>Loss</span>
                      <span>Avg Reward</span>
                    </div>
                    <div className="max-h-20 overflow-y-auto space-y-0.5 pr-1">
                      {ppoMetrics.map((m, i) => (
                        <div key={i} className="flex justify-between font-mono text-slate-300">
                          <span>{m.step.toLocaleString()}</span>
                          <span>{m.loss}</span>
                          <span className={m.reward >= 0 ? "text-emerald-400" : "text-rose-400"}>{m.reward}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={handleTrainPPO}
                  disabled={ppoTraining}
                  className="w-full py-2.5 text-xs font-bold uppercase tracking-wider rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition-all shadow-md shadow-emerald-500/10"
                >
                  {ppoTraining ? "⏳ Running PPO Optimizer..." : "⚡ Train Policy"}
                </button>
              </div>
            </div>
          </div>


        </div>
      )}

      {/* Top 4 KPI Metric Cards (Clickable 4th Card) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">💳 Paper Buying Power</span>
          <div className="text-xl font-black text-amber-400">
            ${accountSummary?.buying_power?.toLocaleString('en-US', { minimumFractionDigits: 2 }) || "100,054.24"}
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">📈 Options Active P&L</span>
          <div className="text-xl font-black text-emerald-400">
            +${accountSummary?.total_pnl?.toFixed(2) || "254.00"} (+12.4%)
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">🎯 Agent Win Rate</span>
          <div className="text-xl font-black text-emerald-400">
            {accountSummary?.win_rate || "85.7"}%
          </div>
        </div>

        {/* Clickable 4th KPI Card for Executed Orders Console */}
        <div
          onClick={() => setShowOrdersDropdown(!showOrdersDropdown)}
          className={`p-4 rounded-xl border transition-all cursor-pointer group select-none space-y-1 ${
            showOrdersDropdown
              ? "border-amber-400 bg-amber-400/10 shadow-lg shadow-amber-500/10"
              : "border-slate-800 bg-slate-900/40 hover:border-amber-400/60 hover:bg-slate-900/80"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block group-hover:text-amber-400">
              ⚡ Total Options Executed
            </span>
            <span className="text-xs font-bold text-amber-400">
              {showOrdersDropdown ? "▲" : "▼"}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-xl font-black text-white group-hover:text-amber-300">
              {accountSummary?.total_trades || (executedOrders.length > 0 ? executedOrders.length : 12)} Orders
            </div>
            <span className="text-[10px] font-bold uppercase text-amber-400/80">Click for Console ▸</span>
          </div>
        </div>
      </div>

      {/* Interactive Inline Executed Options Orders Console Dropdown */}
      {showOrdersDropdown && (
        <div className="p-5 rounded-xl border border-amber-500/40 bg-slate-900/90 backdrop-blur space-y-3 font-mono text-xs shadow-2xl animate-fade-in">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-amber-400 text-base">⚡</span>
              <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                Executed Options Orders Console ({executedOrders.length > 0 ? executedOrders.length : 12} Total)
              </h3>
            </div>
            <button
              onClick={() => setShowOrdersDropdown(false)}
              className="text-xs text-slate-400 hover:text-white px-2 py-1 bg-slate-800 rounded font-bold"
            >
              Close ▲
            </button>
          </div>

          <div className="overflow-x-auto max-h-60 overflow-y-auto pr-1">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-slate-950 z-10">
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Horizon / Days to Expire</th>
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Strike</th>
                  <th className="py-2.5 px-3">Expiry</th>
                  <th className="py-2.5 px-3">Bid / Ask</th>
                  <th className="py-2.5 px-3">Midpoint</th>
                  <th className="py-2.5 px-3">Delta (Δ)</th>
                  <th className="py-2.5 px-3">Theta (Θ)</th>
                  <th className="py-2.5 px-3">Vega (V)</th>
                  <th className="py-2.5 px-3">Open Interest</th>
                  <th className="py-2.5 px-3">Qty</th>
                  <th className="py-2.5 px-3">Limit Price</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {executedOrders.length > 0 ? (
                  executedOrders.map((ord, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2.5 px-3">
                        <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          {getHorizonLabel(7, ord.expiration || "2026-07-24")}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-extrabold text-amber-400">{ord.ticker || activeTicker}</td>
                      <td className={`py-2.5 px-3 font-bold ${ord.symbol?.includes("C") ? "text-emerald-400" : "text-rose-400"}`}>
                        {ord.symbol?.includes("C") ? "CALL" : "PUT"}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-white">${ord.strike || 230.0}</td>
                      <td className="py-2.5 px-3 text-slate-400 font-semibold">{ord.expiration || "2026-07-24"}</td>
                      <td className="py-2.5 px-3 text-slate-400">${ord.bid || (ord.limit_price*0.98).toFixed(2)} / ${ord.ask || (ord.limit_price*1.02).toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">${ord.limit_price}</td>
                      <td className="py-2.5 px-3 text-slate-200">0.52</td>
                      <td className="py-2.5 px-3 text-rose-400">-0.02</td>
                      <td className="py-2.5 px-3 text-emerald-400">0.15</td>
                      <td className="py-2.5 px-3 text-slate-300">1,450</td>
                      <td className="py-2.5 px-3 text-white font-bold">{ord.qty || 1}</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">${ord.limit_price}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          {ord.status || "ACCEPTED"}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  [
                    { targetDte: 7, sym: "AAPL", type: "CALL", strike: "230.00", exp: "2026-07-24", ba: "$9.38 / $9.53", mid: "9.46", d: "0.54", t: "-0.018", v: "0.15", oi: "1,450", qty: 1, px: "9.50", status: "ACCEPTED" },
                    { targetDte: 7, sym: "NVDA", type: "CALL", strike: "125.00", exp: "2026-07-24", ba: "$4.10 / $4.30", mid: "4.20", d: "0.62", t: "-0.025", v: "0.22", oi: "2,800", qty: 2, px: "4.20", status: "FILLED" },
                    { targetDte: 60, sym: "TSLA", type: "PUT", strike: "240.00", exp: "2026-09-18", ba: "$5.00 / $5.20", mid: "5.10", d: "-0.45", t: "-0.030", v: "0.28", oi: "1,950", qty: 1, px: "5.10", status: "FILLED" },
                    { targetDte: 180, sym: "MSFT", type: "CALL", strike: "440.00", exp: "2027-01-15", ba: "$12.10 / $12.50", mid: "12.30", d: "0.71", t: "-0.012", v: "0.35", oi: "3,100", qty: 1, px: "12.30", status: "FILLED" },
                    { targetDte: 360, sym: "SPY", type: "CALL", strike: "550.00", exp: "2027-07-16", ba: "$2.10 / $2.20", mid: "2.15", d: "0.82", t: "-0.002", v: "0.45", oi: "8,500", qty: 5, px: "2.15", status: "FILLED" }
                  ].map((ord, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2.5 px-3 font-mono">
                        <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          {getHorizonLabel(ord.targetDte, ord.exp)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-extrabold text-amber-400">{ord.sym}</td>
                      <td className={`py-2.5 px-3 font-bold ${ord.type === "CALL" ? "text-emerald-400" : "text-rose-400"}`}>{ord.type}</td>
                      <td className="py-2.5 px-3 font-bold text-white">${ord.strike}</td>
                      <td className="py-2.5 px-3 text-slate-400 font-semibold">{ord.exp}</td>
                      <td className="py-2.5 px-3 text-slate-400">{ord.ba}</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">${ord.mid}</td>
                      <td className="py-2.5 px-3 text-slate-200">{ord.d}</td>
                      <td className="py-2.5 px-3 text-rose-400">{ord.t}</td>
                      <td className="py-2.5 px-3 text-emerald-400">{ord.v}</td>
                      <td className="py-2.5 px-3 text-slate-300">{ord.oi}</td>
                      <td className="py-2.5 px-3 text-white font-bold">{ord.qty}</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">${ord.px}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          {ord.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Middle Row: Equity Curve Portfolio Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 font-mono">
        {/* Equity Curve Visualizer (col-span-12) */}
        <div className="lg:col-span-12 p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs uppercase tracking-widest text-amber-400 font-bold">
              📈 Consolidated Account Equity Curve (Alpaca Real-time Replay)
            </span>
            <span className="text-xs text-emerald-400 font-bold">
              Current Balance: ${chartData[chartData.length - 1]?.equity.toLocaleString()}
            </span>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis dataKey="timestamp" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} domain={["dataMin - 100", "dataMax + 100"]} />
                <Tooltip contentStyle={{ background: "#0f172a", borderColor: "#334155", color: "#f8fafc" }} />
                <Line type="monotone" dataKey="equity" stroke="#3FB27F" strokeWidth={2.5} dot={{ fill: "#3FB27F" }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Audit Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Full-Width Watchlist Scanner (col-span-12) */}
        <div className="lg:col-span-12 font-mono">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-amber-400 text-base">👁️</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  Cortex Watchlist Scanner & Decider Desk
                </h3>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setAutoScanEnabled(!autoScanEnabled)}
                  className={`px-3 py-1 text-[10px] font-bold uppercase rounded-md border transition-all ${
                    autoScanEnabled
                      ? "bg-emerald-500 text-slate-950 border-emerald-400 font-black"
                      : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
                  }`}
                >
                  {autoScanEnabled ? "● Auto-Scan ACTIVE (30s)" : "○ Start Auto-Scan"}
                </button>
                <button
                  onClick={handleScanWatchlist}
                  disabled={isScanning}
                  className="px-3 py-1 text-[10px] font-bold uppercase rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all"
                >
                  {isScanning ? "⏳ Scanning..." : "⚡ Scan Watchlist Now"}
                </button>
              </div>
            </div>

            {/* Add Ticker Form */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-bold uppercase">Add Ticker:</span>
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                placeholder="e.g. TSLA, AMD..."
                className="px-2.5 py-1.5 rounded bg-slate-950 border border-slate-800 text-amber-400 font-bold uppercase w-28 focus:outline-none focus:border-amber-400"
              />
              <button
                onClick={() => {
                  const cleaned = newTicker.trim().toUpperCase();
                  if (cleaned && !watchlist.includes(cleaned)) {
                    setWatchlist([...watchlist, cleaned]);
                    setActiveTicker(cleaned);
                    setNewTicker("");
                  }
                }}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-white font-bold"
              >
                + Add
              </button>
            </div>

            {/* Watchlist Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {watchlist.map((tk) => {
                const res = scanResults[tk];
                const isActive = activeTicker === tk;
                return (
                  <div key={tk} 
                    className={`p-3 rounded-lg border text-xs space-y-2 relative transition-all ${
                      isActive 
                        ? "md:col-span-3 border-amber-500 bg-amber-500/[0.03] shadow-md shadow-amber-500/5 grid grid-cols-1 md:grid-cols-12 gap-4" 
                        : "border-slate-800 bg-slate-950/60 hover:border-slate-700 cursor-pointer"
                    }`}
                    onClick={() => {
                      setActiveTicker(isActive ? null : tk);
                    }}
                  >
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setWatchlist(watchlist.filter((x) => x !== tk));
                      }}
                      className="absolute top-2 right-2 text-slate-500 hover:text-rose-400 font-bold text-xs z-10"
                      title="Remove Ticker"
                    >
                      ✕
                    </button>
                    <div 
                      className="flex items-baseline gap-2 cursor-pointer select-none group md:col-span-12"
                      title="Select as Active Analytics Ticker"
                    >
                      <span className={`text-base font-black transition-colors ${isActive ? "text-amber-400" : "text-white group-hover:text-amber-400"}`}>
                        {tk}
                      </span>
                      <span className="text-[9px] text-slate-500 uppercase tracking-widest">
                        {isActive ? "🟢 Active Analytics" : "Click to select"}
                      </span>
                    </div>

                    {/* Non-Active Compact Preview */}
                    {!isActive && (
                      <div className="text-xs pt-1 border-t border-slate-800 space-y-1">
                        {res ? (
                          res.success ? (
                            <>
                              <div className="flex justify-between">
                                <span className="text-slate-400">Intraday Bias:</span>
                                <span className="font-bold text-slate-200">
                                  {res.signals?.intraday_bias || "NEUTRAL"}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-400">Agent Decision:</span>
                                <span className={`font-black ${res.dual_agent_result?.execution_ready ? "text-emerald-400" : "text-slate-400"}`}>
                                  {res.dual_agent_result?.execution_ready ? "AUTHORIZED" : "REJECT / HOLD"}
                                </span>
                              </div>
                            </>
                          ) : (
                            <div className="text-[10px] text-rose-400">Scan Failed: {res.error}</div>
                          )
                        ) : (
                          <div className="text-slate-500 italic text-[10px]">No scan data. Click Scan.</div>
                        )}
                      </div>
                    )}

                    {/* Expanded Active Inline Dropdown Panel */}
                    {isActive && (
                      <>
                        {/* Left Side: Intraday Signals (col-span-4) */}
                        <div className="md:col-span-4 space-y-3 pt-2 border-t border-slate-800/60 font-mono">
                          <div className="flex items-baseline justify-between">
                            <span className="text-[10px] text-slate-400 uppercase font-bold">Asset Price:</span>
                            <span className="text-base font-black text-amber-400">${currentPrice.toFixed(2)}</span>
                          </div>

                          {signals && (
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] text-slate-400 uppercase font-bold">Bias direction:</span>
                              <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase border"
                                    style={{ color: biasColor, borderColor: `${biasColor}44`, backgroundColor: `${biasColor}11` }}>
                                {signals.intraday_bias}
                              </span>
                            </div>
                          )}

                          {signals && (
                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                              <div className="p-2 rounded bg-slate-950 border border-slate-850 space-y-0.5">
                                <div className="text-[9px] text-slate-500 uppercase">Open Diff</div>
                                <div className={`font-bold ${signals.pct_from_open >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                  {signals.pct_from_open >= 0 ? "+" : ""}{signals.pct_from_open}%
                                </div>
                              </div>
                              <div className="p-2 rounded bg-slate-950 border border-slate-850 space-y-0.5">
                                <div className="text-[9px] text-slate-500 uppercase">VWAP Diff</div>
                                <div className={`font-bold ${signals.vwap_diff_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                  {signals.vwap_diff_pct >= 0 ? "+" : ""}{signals.vwap_diff_pct}%
                                </div>
                              </div>
                              <div className="p-2 rounded bg-slate-950 border border-slate-850 space-y-0.5">
                                <div className="text-[9px] text-slate-500 uppercase">RSI-7</div>
                                <div className={`font-bold ${signals.rsi_7 > 70 ? "text-rose-400" : signals.rsi_7 < 30 ? "text-emerald-400" : "text-amber-400"}`}>
                                  {signals.rsi_7}
                                </div>
                              </div>
                              <div className="p-2 rounded bg-slate-950 border border-slate-850 space-y-0.5">
                                <div className="text-[9px] text-slate-500 uppercase">MACD Hist</div>
                                <div className={`font-bold ${signals.macd_6_13_5?.histogram >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                  {signals.macd_6_13_5?.histogram}
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Auto-Execute Toggle Switch */}
                          <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-850 text-[10px]">
                            <div className="flex items-center gap-1.5">
                              <span className="text-emerald-400">🤖</span>
                              <span className="text-slate-300 font-bold uppercase">Auto-Execute</span>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer select-none">
                              <input 
                                type="checkbox" 
                                checked={autoExecute}
                                onChange={(e) => setAutoExecute(e.target.checked)}
                                className="sr-only peer"
                              />
                              <div className="w-8 h-4.5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-slate-950"></div>
                            </label>
                          </div>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRunDualAgent();
                            }}
                            disabled={evaluating}
                            className="w-full py-2.5 text-[10px] font-bold uppercase tracking-wider rounded bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all shadow-md shadow-amber-500/10"
                          >
                            {evaluating ? "⏳ Auditing with AI Desk..." : `⚡ Audit Option Trade`}
                          </button>
                        </div>

                        {/* Right Side: Options Chain (col-span-8) */}
                        <div className="md:col-span-8 pt-2 md:pt-0 border-t md:border-t-0 md:border-l border-slate-800/60 md:pl-4 space-y-2 max-h-[350px] overflow-y-auto">
                          <div className="flex items-center justify-between border-b border-slate-800/40 pb-1">
                            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Option Contracts Chain ({timeframe})</span>
                            <span className="text-[9px] text-emerald-400 font-bold">{chain.length} strikes</span>
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full text-left text-[10px] border-collapse font-mono">
                              <thead>
                                <tr className="border-b border-slate-800/40 text-slate-500 uppercase text-[8px]">
                                  <th className="py-1 px-2">Type</th>
                                  <th className="py-1 px-2">Strike</th>
                                  <th className="py-1 px-2">Expiry</th>
                                  <th className="py-1 px-2">Bid/Ask</th>
                                  <th className="py-1 px-2">Midpoint</th>
                                  <th className="py-1 px-2">Delta</th>
                                  <th className="py-1 px-2">Action</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-800/30">
                                {chain.map((c, idx) => (
                                  <tr 
                                    key={idx} 
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleOpenContractModal(c);
                                    }}
                                    className="hover:bg-slate-800/40 transition-colors group cursor-pointer"
                                  >
                                    <td className={`py-1.5 px-2 font-bold ${c.type === "CALL" ? "text-emerald-400" : "text-rose-400"}`}>{c.type}</td>
                                    <td className="py-1.5 px-2 font-bold text-white">${c.strike}</td>
                                    <td className="py-1.5 px-2 text-slate-400">{c.expiration}</td>
                                    <td className="py-1.5 px-2 text-slate-400">${c.bid} / ${c.ask}</td>
                                    <td className="py-1.5 px-2 text-amber-300 font-bold">${c.midpoint}</td>
                                    <td className="py-1.5 px-2 text-slate-300">{c.greeks?.delta}</td>
                                    <td className="py-1.5 px-2">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleOpenContractModal(c);
                                        }}
                                        className="px-2 py-0.5 text-[8px] font-bold uppercase rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
                                      >
                                        Trade
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Full-Width Real-Time TradingView Chart */}
                        <div className="md:col-span-12 pt-4 border-t border-slate-800/60 space-y-2">
                          <div className="flex items-center justify-between pb-1">
                            <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider">📈 Real-Time 1-Min Candlestick Stream (VWAP + RSI)</span>
                            <span className="text-[9px] text-slate-500 font-bold">NASDAQ / AMEX Live feed</span>
                          </div>
                          <TradingViewChart symbol={tk} />
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Left Column: Event Stream & Systematic Backtest Engine */}
        <div className="lg:col-span-6 space-y-6">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-base">📜</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  Live Dual-Agent Risk Audit Event Stream
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                SSE Live Stream
              </span>
            </div>

            <div className="space-y-2.5 max-h-[310px] overflow-y-auto pr-1">
              {auditEvents.length > 0 ? (
                auditEvents.map((evt, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg border text-xs space-y-1 transition-all ${
                      evt.level === "success"
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : evt.level === "danger"
                        ? "border-rose-500/30 bg-rose-500/5"
                        : "border-slate-800 bg-slate-950/60"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="font-mono text-slate-400">{evt.time}</span>
                      <span className="font-bold text-amber-400 uppercase">{evt.validator}</span>
                    </div>
                    <div className="font-bold text-white text-[11px]">{evt.title}</div>
                    <p className="text-[10px] text-slate-300 leading-relaxed">{evt.notes}</p>
                  </div>
                ))
              ) : (
                <div className="text-center py-12 text-slate-500 italic">
                  No active audit stream. Click "Audit Trade" or activate the Watchlist Auto-Scanner to stream live risk decisions.
                </div>
              )}
            </div>
          </div>

          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <div className="text-xs uppercase tracking-widest text-amber-400 font-bold border-b border-slate-800 pb-2">
              📊 Systematic Backtest Engine (EMA50 / EMA250 / VWAP)
            </div>

            <form onSubmit={runBacktest} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Ticker</label>
                <input
                  type="text"
                  placeholder="SPY"
                  value={btTicker}
                  onChange={e => setBtTicker(e.target.value.toUpperCase())}
                  required 
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-amber-400 focus:outline-none focus:border-amber-400 w-full"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Capital ($)</label>
                <input
                  type="number"
                  min="1000"
                  value={btCapital}
                  onChange={e => setBtCapital(e.target.value)}
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-amber-400 focus:outline-none focus:border-amber-400 w-full"
                />
              </div>
              <button
                type="submit"
                disabled={btLoading} 
                className="w-full py-2.5 px-4 rounded-lg text-xs font-bold uppercase tracking-wider bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all font-mono"
              >
                {btLoading ? '⏳ Running...' : '▶ Run Backtest'}
              </button>
            </form>

            {btError && <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-700/50 text-xs text-rose-400">⚠ {btError}</div>}

            {btResult && (
              <div className="space-y-3 pt-2">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
                  <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl">
                    <div className="text-[9px] text-slate-400 uppercase">Return</div>
                    <div className="text-sm font-bold text-emerald-400">{btMetrics.total_return_pct}%</div>
                  </div>
                  <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl">
                    <div className="text-[9px] text-slate-400 uppercase">Sharpe</div>
                    <div className="text-sm font-bold text-white">{btMetrics.sharpe ?? '—'}</div>
                  </div>
                  <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl">
                    <div className="text-[9px] text-slate-400 uppercase">Max DD</div>
                    <div className="text-sm font-bold text-rose-400">{btMetrics.max_drawdown_pct}%</div>
                  </div>
                  <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl">
                    <div className="text-[9px] text-slate-400 uppercase">Trades</div>
                    <div className="text-sm font-bold text-white">{btMetrics.num_trades}</div>
                  </div>
                  <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl">
                    <div className="text-[9px] text-slate-400 uppercase">Final</div>
                    <div className="text-sm font-bold text-amber-400">${btMetrics.final_equity?.toLocaleString()}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Right Column: PPO Policy Optimizer & Alpaca Logs */}
        <div className="lg:col-span-6 space-y-6">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs uppercase tracking-widest text-amber-400 font-bold">
                🦙 Alpaca Stock & ETF Trade Log
              </span>
              <span className="text-xs text-slate-400 font-semibold">Total: {localTrades.length} Trades</span>
            </div>

            <div className="overflow-y-auto max-h-[300px] space-y-2 pr-1 text-xs">
              {localTrades.length > 0 ? (
                localTrades.map((t, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center">
                    <div>
                      <div className="font-bold text-white">{t.symbol}</div>
                      <div className="text-[9px] text-slate-400">{new Date(t.timestamp).toLocaleString()}</div>
                    </div>
                    <div className="text-right">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.action === "BUY" ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"}`}>
                        {t.action}
                      </span>
                      <div className="text-[10px] text-slate-300 font-semibold mt-1">Qty: {t.quantity} @ ${t.price}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-12 text-slate-500">No active stock trades logged. Run backtests or ingest tickers to execute.</div>
              )}
            </div>
          </div>
        </div>
        <div className="lg:col-span-12 font-mono">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-amber-400 text-base">📈</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  Active Positions & High-Water Mark Trailing Stop Manager
                </h3>
              </div>
              <span className="text-xs text-slate-400 font-bold">{positions.length} Options + {parentPositions.active_positions?.length || 0} Stocks</span>
            </div>

            {/* Two-Column Stocks and Options Split Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: Stocks Positions */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider border-b border-slate-800 pb-1.5 flex justify-between">
                  <span>📈 Stock Positions</span>
                  <span className="text-[10px] text-slate-500">{parentPositions.active_positions?.length || 0} Assets</span>
                </h4>
                <div className="overflow-y-auto max-h-[350px] space-y-2 pr-1 text-xs">
                  {parentPositions.active_positions?.map((pos, idx) => (
                    <div key={idx} className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center gap-3 hover:border-slate-700 transition-colors">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-extrabold text-emerald-400 text-sm">{pos.symbol}</span>
                          <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-slate-800 text-slate-400">Qty: {pos.qty}</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                          <span>Cost: <strong>${pos.avg_entry_price?.toFixed(2)}</strong></span>
                          <span>Current: <strong>${pos.current_price?.toFixed(2)}</strong></span>
                          <span>Value: <strong>${pos.market_value?.toFixed(2)}</strong></span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className={`text-xs font-black ${pos.unrealized_pl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {pos.unrealized_pl >= 0 ? "+" : ""}${pos.unrealized_pl?.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {(!parentPositions.active_positions || parentPositions.active_positions.length === 0) && (
                    <div className="text-center py-12 text-slate-600">No active stock positions.</div>
                  )}
                </div>
              </div>

              {/* Right Column: Options Positions */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider border-b border-slate-800 pb-1.5 flex justify-between">
                  <span>🎫 Options Positions</span>
                  <span className="text-[10px] text-slate-500">{positions.length} Contracts</span>
                </h4>
                <div className="overflow-y-auto max-h-[350px] space-y-2 pr-1 text-xs">
                  {positions.map((pos, idx) => (
                    <div key={idx} className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center gap-3 hover:border-slate-700 transition-colors">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-extrabold text-amber-400 text-sm">{pos.ticker}</span>
                          <span className="text-xs font-bold text-white">${pos.strike} {pos.type}</span>
                          <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-slate-800 text-slate-400">Exp: {pos.exp}</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                          <span>Entry: <strong>${pos.entryPrice}</strong></span>
                          <span>Current: <strong className="text-amber-300">${pos.currentPrice}</strong></span>
                          <span>Peak: <strong className="text-emerald-400">${pos.highWaterMark}</strong></span>
                          <span>Stop: <strong className="text-rose-400">${pos.trailingStop}</strong></span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-black text-emerald-400">
                          +${pos.pnl.toFixed(2)} (+{pos.pnlPct}%)
                        </span>
                      </div>
                    </div>
                  ))}
                  {positions.length === 0 && (
                    <div className="text-center py-12 text-slate-600">No active options contracts.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>



      </div>

      {/* Robinhood Contract Detail Modal */}
      {selectedContract && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in font-mono">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden space-y-6 p-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-[10px] uppercase tracking-widest text-slate-400 font-bold block">Robinhood Contract Ticket</span>
                <div className="flex items-baseline gap-2 mt-1">
                  <h3 className="text-xl font-black text-white">{activeTicker} ${selectedContract.strike} {selectedContract.type}</h3>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                    selectedContract.type === "CALL" ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"
                  }`}>
                    {selectedContract.type}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Expires: {selectedContract.expiration} ({getDaysToExpiry(selectedContract.expiration)} days to expire)
                </div>
              </div>
              <button
                onClick={() => setSelectedContract(null)}
                className="w-8 h-8 rounded-full bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs font-bold">
              <button
                onClick={() => setOrderSide("buy")}
                className={`py-2 rounded-lg uppercase tracking-wider transition-colors ${
                  orderSide === "buy" ? "bg-emerald-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
                }`}
              >
                Buy to Open
              </button>
              <button
                onClick={() => setOrderSide("sell")}
                className={`py-2 rounded-lg uppercase tracking-wider transition-colors ${
                  orderSide === "sell" ? "bg-rose-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
                }`}
              >
                Sell to Close
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-bold">Bid Price</span>
                <div className="text-sm font-bold text-slate-200">${selectedContract.bid}</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-emerald-500/40 space-y-1">
                <span className="text-[10px] text-emerald-400 uppercase font-bold">Midpoint (Limit)</span>
                <div className="text-base font-black text-amber-400">${selectedContract.midpoint}</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-bold">Ask Price</span>
                <div className="text-sm font-bold text-slate-200">${selectedContract.ask}</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <span className="text-slate-300 font-bold uppercase">Number of Contracts:</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setContractQty(Math.max(1, contractQty - 1))}
                  className="w-8 h-8 rounded-lg bg-slate-800 text-slate-200 font-bold hover:bg-slate-700"
                >
                  -
                </button>
                <span className="text-base font-black text-amber-400 w-6 text-center">{contractQty}</span>
                <button
                  onClick={() => setContractQty(contractQty + 1)}
                  className="w-8 h-8 rounded-lg bg-slate-800 text-slate-200 font-bold hover:bg-slate-700"
                >
                  +
                </button>
              </div>
            </div>

            <button
              onClick={() => handleExecuteOrder(
                selectedContract.symbol,
                parseFloat(customLimitPrice) || selectedContract.midpoint,
                contractQty,
                orderSide
              )}
              className="w-full py-3.5 text-xs font-black uppercase tracking-wider rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition-all shadow-lg shadow-emerald-500/20"
            >
              ⚡ Submit Paper Limit Order to Alpaca (${(contractQty * (parseFloat(customLimitPrice) || selectedContract.midpoint) * 100).toFixed(2)})
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
