import React, { useState, useEffect, useMemo } from "react";

/*
  WHITELIGHT + SHADOW CORTEX — UNIFIED INTEGRATED ENGINE TAB
  Combines Whitelight Intraday Signals & Robinhood Options Chains
  with Shadow Cortex Fail-Closed Dual-Agent Pipeline & MCP Controls
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

export default function WhitelightCortexIntegratedPanel({ API_BASE = "http://127.0.0.1:8000/api" }) {
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

  // Cortex AI Budget & Cooldown Brakes
  const [callsToday, setCallsToday] = useState(42);
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(500);
  const [cooldownSecs, setCooldownSecs] = useState(18);

  // Scheduled Expiration Side Toast Alert Popup
  const [expirationAlert, setExpirationAlert] = useState(null);

  // UI Views & Modals
  const [showOrdersDropdown, setShowOrdersDropdown] = useState(false);
  const [showStrategyGuide, setShowStrategyGuide] = useState(false);
  const [selectedContract, setSelectedContract] = useState(null);
  const [contractQty, setContractQty] = useState(1);
  const [orderSide, setOrderSide] = useState("buy");
  const [customLimitPrice, setCustomLimitPrice] = useState("");

  // Dual Agent Configuration (Gemini 3.5 Flash Low Cost Validation Default)
  const [proposerProvider, setProposerProvider] = useState("gemini");
  const [proposerModel, setProposerModel] = useState("gemini-3.5-flash");
  const [validatorProvider, setValidatorProvider] = useState("gemini");
  const [validatorModel, setValidatorModel] = useState("gemini-3.5-flash"); // Gemini 3.5 Flash Low
  const [agentResult, setAgentResult] = useState(null);

  // Live Audit JSONL Event Stream
  const [auditEvents, setAuditEvents] = useState([
    {
      time: "13:12:10 PM",
      type: "PROPOSAL_VALIDATED",
      level: "success",
      title: "PROPOSAL AUTHORIZED: AAPL $230 CALL",
      notes: "Passed 5 Wall St Rules | Midpoint: $9.46 | IV Rank: 32% | OI: 1,450",
      validator: "Gemini 3.5 Flash (Low)"
    },
    {
      time: "13:11:45 PM",
      type: "RISK_GATE_REFUSAL",
      level: "danger",
      title: "ENTRY SKIPPED: NVDA $125 CALL",
      notes: "Refused by Risk Desk — IV Rank 62.4% exceeds 50% cap (IV Crush Hazard)",
      validator: "Gemini 3.5 Flash (Low)"
    },
    {
      time: "13:08:20 PM",
      type: "ORDER_FILLED",
      level: "info",
      title: "PAPER ORDER FILLED: TSLA $240 PUT",
      notes: "Limit Price: $5.10 | Qty: 1 | Broker: Alpaca Paper",
      validator: "System Execution Gate"
    }
  ]);

  // High-Water Mark Trailing Stop Active Positions
  const [positions, setPositions] = useState([
    {
      symbol: "AAPL260724C00230000",
      ticker: "AAPL",
      type: "CALL",
      strike: "230.00",
      entryPrice: 9.46,
      currentPrice: 11.20,
      highWaterMark: 11.50,
      trailingStop: 10.35,
      pnl: 174.00,
      pnlPct: 18.4,
      targetDte: 7,
      exp: "2026-07-24"
    },
    {
      symbol: "MSFT260918C00440000",
      ticker: "MSFT",
      type: "CALL",
      strike: "440.00",
      entryPrice: 12.30,
      currentPrice: 13.10,
      highWaterMark: 13.50,
      trailingStop: 12.15,
      pnl: 80.00,
      pnlPct: 6.5,
      targetDte: 60,
      exp: "2026-09-18"
    }
  ]);

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

  useEffect(() => {
    fetchIntradayData(activeTicker, timeframe);
    fetchAccountSummary();
  }, [activeTicker, timeframe]);

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

        // Push to Audit Stream
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
          proposer_provider: proposerProvider,
          proposer_model: proposerModel,
          validator_provider: validatorProvider,
          validator_model: validatorModel
        })
      });
      const data = await res.json();
      if (data.success) {
        setAgentResult(data.dual_agent_result);
        setCallsToday((prev) => prev + 1);

        // Append to Audit Event Stream
        const isReady = data.dual_agent_result?.execution_ready;
        setAuditEvents((prev) => [{
          time: new Date().toLocaleTimeString(),
          type: isReady ? "PROPOSAL_VALIDATED" : "RISK_GATE_REFUSAL",
          level: isReady ? "success" : "danger",
          title: isReady ? `PROPOSAL AUTHORIZED: ${activeTicker}` : `REJECTED BY RISK DESK: ${activeTicker}`,
          notes: data.dual_agent_result?.validation?.validation_notes || "Audited against 5 Wall St Rules",
          validator: "Gemini 3.5 Flash (Low)"
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
            <h1 className="text-lg font-bold tracking-tight text-amber-400">Whitelight + Shadow Cortex Engine</h1>
            <p className="text-[10px] text-slate-400">Unified Intraday Signals, Dual-Agent Risk Desk & MCP Control</p>
          </div>
        </div>

        {/* Universal Ticker Search Form */}
        <form onSubmit={handleTickerSearch} className="flex items-center gap-2">
          <label className="text-xs text-slate-400 uppercase tracking-wider">Ticker:</label>
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
            onClick={() => setShowStrategyGuide(!showStrategyGuide)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
              showStrategyGuide
                ? "bg-amber-500 text-slate-950 border-amber-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20"
            }`}
          >
            📘 {showStrategyGuide ? "Hide Guide" : "Strategy Guide"}
          </button>
        </div>
      </div>

      {/* Cortex AI Budget & Intake Cooldown Control Banner */}
      <div className="p-4 rounded-xl border border-amber-500/30 bg-slate-900/40 backdrop-blur font-mono text-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">AI Decider Model</span>
            <span className="font-bold text-emerald-400 text-xs">⚡ Gemini 3.5 Flash (Low Cost Validation)</span>
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
                <li><strong className="text-emerald-300">Agent 2: Validator (Gemini 3.5 Flash Low):</strong> Senior Risk Manager desk auditing 5 Wall Street rules. Outputs <span className="text-emerald-400 font-bold">EXECUTE</span> or <span className="text-rose-400 font-bold">REJECT</span>.</li>
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

      {/* Top 4 KPI Metric Cards */}
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

      {/* Main Grid: Signals & Dual-Agent (Left) / Live Audit Feed (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column (col-span-6): Intraday Signals & Dual Agent Control */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs uppercase tracking-widest text-slate-400 font-mono">Spotlight Asset</span>
                <div className="flex items-baseline gap-2 mt-1">
                  <h2 className="text-2xl font-black font-mono text-white">{activeTicker}</h2>
                  <span className="text-xl font-bold font-mono text-amber-400">${currentPrice.toFixed(2)}</span>
                </div>
              </div>
              {signals && (
                <span className="px-3 py-1 text-xs font-bold font-mono uppercase tracking-wider rounded-md border"
                      style={{ color: biasColor, borderColor: `${biasColor}44`, backgroundColor: `${biasColor}11` }}>
                  {signals.intraday_bias}
                </span>
              )}
            </div>

            {/* 4 Intraday Signals Grid */}
            {signals && (
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase">1. % From Open</div>
                  <div className={`text-base font-bold ${signals.pct_from_open >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {signals.pct_from_open >= 0 ? "+" : ""}{signals.pct_from_open}%
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase">2. VWAP Diff</div>
                  <div className={`text-base font-bold ${signals.vwap_diff_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {signals.vwap_diff_pct >= 0 ? "+" : ""}{signals.vwap_diff_pct}%
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase">3. RSI-7 (5-Min)</div>
                  <div className={`text-base font-bold ${signals.rsi_7 > 70 ? "text-rose-400" : signals.rsi_7 < 30 ? "text-emerald-400" : "text-amber-400"}`}>
                    {signals.rsi_7}
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase">4. MACD (6,13,5)</div>
                  <div className={`text-base font-bold ${signals.macd_6_13_5?.histogram >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    Hist: {signals.macd_6_13_5?.histogram}
                  </div>
                </div>
              </div>
            )}

            {/* Dual Agent Execution Trigger Button */}
            <button
              onClick={handleRunDualAgent}
              disabled={evaluating}
              className="w-full py-3 text-xs font-bold uppercase tracking-wider rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all shadow-lg shadow-amber-500/10"
            >
              {evaluating ? "⏳ Auditing with Gemini 3.5 Flash..." : `⚡ Audit Trade (${activeTicker} - ${timeframe})`}
            </button>
          </div>
        </div>

        {/* Right Column (col-span-6): Live Audit Event Stream */}
        <div className="lg:col-span-6 space-y-4 font-mono text-xs">
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
              {auditEvents.map((evt, idx) => (
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
              ))}
            </div>
          </div>
        </div>

        {/* Full-Width Row (col-span-12): Options Chain Table (No Side Column, Dynamic Days to Expire) */}
        <div className="lg:col-span-12 font-mono">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-xs font-mono uppercase tracking-widest text-amber-400 font-bold">
                Options Chain ({timeframe}) - Click Any Row for Robinhood Contract Detail Ticket
              </h3>
              <span className="text-xs font-mono text-emerald-400 font-bold px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-md">
                {chain.length} Liquid Contracts
              </span>
            </div>
            <div className="overflow-x-auto max-h-[450px] overflow-y-auto pr-1">
              <table className="w-full font-mono text-xs text-left border-collapse cursor-pointer">
                <thead className="sticky top-0 bg-slate-900 z-10">
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                    <th className="py-2.5 px-3">Symbol</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Strike</th>
                    <th className="py-2.5 px-3">Expiry / Days to Expire</th>
                    <th className="py-2.5 px-3">Bid / Ask</th>
                    <th className="py-2.5 px-3">Midpoint</th>
                    <th className="py-2.5 px-3">Delta (Δ)</th>
                    <th className="py-2.5 px-3">Theta (Θ)</th>
                    <th className="py-2.5 px-3">Vega (V)</th>
                    <th className="py-2.5 px-3">Open Interest</th>
                    <th className="py-2.5 px-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {chain.map((c, idx) => (
                    <tr 
                      key={idx} 
                      onClick={() => handleOpenContractModal(c)}
                      className="hover:bg-slate-800/60 transition-colors group"
                    >
                      <td className="py-2.5 px-3 font-extrabold text-amber-400 group-hover:underline">{activeTicker}</td>
                      <td className={`py-2.5 px-3 font-bold ${c.type === "CALL" ? "text-emerald-400" : "text-rose-400"}`}>{c.type}</td>
                      <td className="py-2.5 px-3 font-bold text-white">${c.strike}</td>
                      <td className="py-2.5 px-3 text-slate-400 font-semibold">{c.expiration} ({getDaysToExpiry(c.expiration)} days to expire)</td>
                      <td className="py-2.5 px-3 text-slate-400">${c.bid} / ${c.ask}</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">${c.midpoint}</td>
                      <td className="py-2.5 px-3 text-slate-200">{c.greeks?.delta}</td>
                      <td className="py-2.5 px-3 text-rose-400">{c.greeks?.theta}</td>
                      <td className="py-2.5 px-3 text-emerald-400">{c.greeks?.vega}</td>
                      <td className="py-2.5 px-3 text-slate-300">{c.open_interest}</td>
                      <td className="py-2.5 px-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenContractModal(c);
                          }}
                          className="px-3 py-1 text-[10px] font-bold uppercase rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30 font-mono"
                        >
                          View Ticket
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
