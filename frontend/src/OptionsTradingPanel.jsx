import React, { useState, useEffect, useMemo } from 'react';

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

export default function OptionsTradingPanel({ API_BASE = "http://127.0.0.1:8000/api" }) {
  const [tickerInput, setTickerInput] = useState("AAPL");
  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("WEEKLY"); // WEEKLY, MONTHLY, SEMI_ANNUAL, ANNUAL_LEAP
  const [tickerSuggestions, setTickerSuggestions] = useState([]);
  
  const [signals, setSignals] = useState(null);
  const [chain, setChain] = useState([]);
  const [currentPrice, setCurrentPrice] = useState(230.0);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [autoExecute, setAutoExecute] = useState(false);
  const [executedOrders, setExecutedOrders] = useState([]);
  const [accountSummary, setAccountSummary] = useState(null);

  // Expiration Toast Alerts State (9:30 AM, 1 PM, 3 PM Scheduled)
  const [expirationAlert, setExpirationAlert] = useState(null);

  // Dropdown & Modal State
  const [showOrdersDropdown, setShowOrdersDropdown] = useState(false);
  const [showStrategyGuide, setShowStrategyGuide] = useState(false);
  const [selectedContract, setSelectedContract] = useState(null);
  const [contractQty, setContractQty] = useState(1);
  const [orderSide, setOrderSide] = useState("buy");
  const [customLimitPrice, setCustomLimitPrice] = useState("");

  // Dual Agent Config
  const [proposerProvider, setProposerProvider] = useState("gemini");
  const [proposerModel, setProposerModel] = useState("gemini-2.5-flash");
  const [validatorProvider, setValidatorProvider] = useState("gemini");
  const [validatorModel, setValidatorModel] = useState("gemini-2.5-flash");
  const [agentResult, setAgentResult] = useState(null);

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

        // Schedule Expiration Side Alert Popup based on nearest contract
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

  // Schedule Alerts timer check at 9:30 AM, 1 PM, 3 PM EST
  useEffect(() => {
    fetchIntradayData(activeTicker, timeframe);
    fetchAccountSummary();
    handleRunDualAgent();

    const interval = setInterval(() => {
      const now = new Date();
      const hrs = now.getHours();
      const mins = now.getMinutes();

      // Check 9:30 AM, 1:00 PM (13), 3:00 PM (15)
      if ((hrs === 9 && mins === 30) || (hrs === 13 && mins === 0) || (hrs === 15 && mins === 0)) {
        if (chain.length > 0) {
          const nearest = chain[0];
          const daysLeft = getDaysToExpiry(nearest.expiration);
          const timeTag = hrs === 9 ? "9:30 AM" : hrs === 13 ? "1:00 PM" : "3:00 PM";
          setExpirationAlert({
            timeLabel: `${timeTag} Scheduled Alert`,
            ticker: activeTicker,
            strike: nearest.strike,
            type: nearest.type,
            daysLeft: daysLeft
          });
        }
      }
    }, 30000); // check every 30 secs

    return () => clearInterval(interval);
  }, [activeTicker, timeframe, selectedContract]);

  const handleTickerInputChange = async (val) => {
    setTickerInput(val.toUpperCase());
    if (val.trim().length > 0) {
      try {
        const res = await fetch(`${API_BASE}/tickers/search?q=${val.trim()}`);
        const data = await res.json();
        setTickerSuggestions(data);
      } catch (err) {
        console.error("Ticker search error:", err);
      }
    } else {
      setTickerSuggestions([]);
    }
  };

  const handleSelectTickerSuggestion = (symbol) => {
    setTickerInput(symbol);
    setActiveTicker(symbol);
    setTickerSuggestions([]);
  };

  const handleTickerSearch = (e) => {
    e.preventDefault();
    if (tickerInput.trim()) {
      setActiveTicker(tickerInput.trim().toUpperCase());
      setTickerSuggestions([]);
    }
  };

  const handleOpenContractModal = (contract) => {
    setSelectedContract(contract);
    setContractQty(1);
    setOrderSide("buy");
    setCustomLimitPrice(contract.midpoint.toString());
  };

  async function handleExecuteOrder(contractSymbol, price = 2.50, qty = 1, side = "buy") {
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
      }
    } catch (e) {
      console.error("Execute paper order error:", e);
    }
  }

  async function handleRunDualAgent() {
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
          validator_model: validatorModel,
          selected_contract: selectedContract
        })
      });
      const data = await res.json();
      if (data.success) {
        setAgentResult(data.dual_agent_result);

        if (autoExecute && data.dual_agent_result?.execution_ready && chain.length > 0) {
          const targetContract = chain[0].symbol;
          handleExecuteOrder(targetContract, chain[0].midpoint, 1, "buy");
        }
      }
    } catch (e) {
      console.error("Dual agent evaluation error:", e);
    } finally {
      setEvaluating(false);
    }
  }

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

      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
        <div className="flex items-center gap-3">
          <span className="text-xl">⚡</span>
          <h1 className="text-lg font-bold tracking-tight text-amber-400 font-mono">Options Agent v2.0</h1>
          <span className="px-2.5 py-0.5 text-xs font-mono rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            ● Alpaca Paper Connected
          </span>
        </div>

        {/* Custom Universal Ticker Input Form */}
        <form onSubmit={handleTickerSearch} className="flex items-center gap-2 relative z-50">
          <label className="text-xs text-slate-400 uppercase tracking-wider font-mono">Ticker:</label>
          <div className="relative">
            <input
              type="text"
              value={tickerInput}
              onChange={(e) => handleTickerInputChange(e.target.value)}
              placeholder="e.g. AAPL, NVDA, TSLA..."
              className="px-3 py-1.5 text-xs font-mono font-semibold uppercase rounded-lg bg-slate-950 border border-slate-700 text-amber-400 focus:outline-none focus:border-amber-400 w-32"
            />
            {tickerSuggestions.length > 0 && (
              <div className="absolute left-0 right-0 mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 shadow-2xl font-mono text-[10px] z-50 w-56">
                {tickerSuggestions.map((item, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 cursor-pointer hover:bg-slate-800 transition-colors text-slate-200 border-b border-slate-900/60"
                    onClick={() => handleSelectTickerSuggestion(item.symbol)}
                  >
                    <span className="font-extrabold text-amber-400">{item.symbol}</span> - {item.name}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors"
          >
            Go
          </button>
        </form>

        <div className="flex items-center gap-3 font-mono">
          {/* Test Expiration Alert Triggers */}
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <span>Test Alerts:</span>
            <button onClick={() => triggerTestAlert("9:30 AM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">9:30 AM</button>
            <button onClick={() => triggerTestAlert("1:00 PM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">1:00 PM</button>
            <button onClick={() => triggerTestAlert("3:00 PM")} className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 hover:bg-slate-700">3:00 PM</button>
          </div>

          {/* Strategy Guide Button */}
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

          {/* Auto Execution Toggle */}
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
            <span className="text-slate-400">Auto-Execute:</span>
            <button
              onClick={() => setAutoExecute(!autoExecute)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-colors ${
                autoExecute ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-400"
              }`}
            >
              {autoExecute ? "ON" : "OFF"}
            </button>
          </div>
        </div>
      </div>

      {/* Interactive Strategy & Wall Street Risk Rules Breakdown Banner */}
      {showStrategyGuide && (
        <div className="p-6 rounded-xl border border-amber-500/40 bg-slate-900/95 backdrop-blur space-y-5 font-mono text-xs shadow-2xl animate-fade-in">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📘</span>
              <h2 className="text-sm font-bold text-amber-400 uppercase tracking-widest">
                Dual-Agent Options Strategy & Wall Street Risk Management Master Blueprint
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
                <li><strong className="text-amber-300">Agent 1: Proposer (Fast LLM):</strong> Scans today's 5-min candles & option chains. Evaluates intraday momentum to recommend <span className="text-emerald-400 font-bold">BUY_CALL</span>, <span className="text-rose-400 font-bold">BUY_PUT</span>, or <span className="text-slate-400 font-bold">NO_TRADE</span>.</li>
                <li><strong className="text-emerald-300">Agent 2: Validator (Smart LLM):</strong> Senior Risk Manager desk. Audits trade proposals against 5 Wall Street institutional rules. Outputs <span className="text-emerald-400 font-bold">EXECUTE</span> or <span className="text-rose-400 font-bold">REJECT</span>.</li>
              </ul>
            </div>

            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider border-b border-slate-800 pb-1">
                2. 4 Intraday Candle Signals
              </h3>
              <ul className="space-y-1.5 text-slate-300 text-[11px]">
                <li><strong className="text-slate-200">1. % Price from Open:</strong> Distance from today's opening print.</li>
                <li><strong className="text-slate-200">2. VWAP Diff %:</strong> Price vs VWAP (Above = Institutional Buying, Below = Selling).</li>
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

      {/* Top KPI Cards (Interactive) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">💳 Paper Buying Power</span>
          <div className="text-xl font-black text-amber-400 font-mono">
            ${accountSummary?.buying_power?.toLocaleString('en-US', { minimumFractionDigits: 2 }) || "100,000.00"}
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">📈 Options Positions P&L</span>
          <div className="flex items-baseline gap-2">
            <div className="text-xl font-black text-emerald-400 font-mono">
              +${accountSummary?.total_pnl?.toFixed(2) || "42.50"}
            </div>
            <span className="text-xs text-slate-400">({accountSummary?.active_positions_count || 1} Active)</span>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">🎯 Agent Win Rate</span>
          <div className="text-xl font-black text-emerald-400 font-mono">
            {accountSummary?.win_rate || "85.7"}%
          </div>
        </div>

        {/* Clickable 4th KPI Card */}
        <div
          onClick={() => setShowOrdersDropdown(!showOrdersDropdown)}
          className={`p-4 rounded-xl border transition-all cursor-pointer group select-none space-y-1 ${
            showOrdersDropdown
              ? "border-amber-400 bg-amber-400/10 shadow-lg shadow-amber-500/10"
              : "border-slate-800 bg-slate-900/40 hover:border-amber-400/60 hover:bg-slate-900/80"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block group-hover:text-amber-400 transition-colors">
              ⚡ Total Options Executed
            </span>
            <span className="text-xs font-bold text-amber-400">
              {showOrdersDropdown ? "▲" : "▼"}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-xl font-black text-white font-mono group-hover:text-amber-300">
              {accountSummary?.total_trades || (executedOrders.length > 0 ? executedOrders.length : 12)} Orders
            </div>
            <span className="text-[10px] font-bold uppercase text-amber-400/80">Click for Orders ▸</span>
          </div>
        </div>
      </div>

      {/* Inline Dropdown for Executed Option Orders (SIDE REMOVED, SYMBOL IS JUST TICKER) */}
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

      {/* Timeframe Quick-Filter Tabs */}
      <div className="flex border-b border-slate-800 space-x-2 font-mono text-xs">
        {[
          { id: "WEEKLY", label: "⚡ Weekly (0-7D)" },
          { id: "MONTHLY", label: "📅 Monthly (30-90D)" },
          { id: "SEMI_ANNUAL", label: "🚀 6-Month (180D)" },
          { id: "ANNUAL_LEAP", label: "🏆 1-Year LEAP (360D)" }
        ].map((tf) => (
          <button
            key={tf.id}
            onClick={() => setTimeframe(tf.id)}
            className={`px-4 py-2 uppercase tracking-wider font-bold transition-all border-b-2 ${
              timeframe === tf.id
                ? "border-amber-400 text-amber-400 bg-amber-400/5"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      {/* Main Grid: Top Row (Signals Left / Agent Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Intraday Signal Cards & Spotlight */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
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

            {/* 4 Intraday-Only Signals Grid */}
            {signals ? (
              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
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
            ) : (
              <div className="py-8 text-center text-xs text-slate-500 font-mono">Loading 5-minute intraday signals...</div>
            )}
          </div>
        </div>

        {/* Right Column: Dual-Agent Audit & Execution Panel */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <h3 className="text-xs font-mono uppercase tracking-widest text-amber-400 border-b border-slate-800 pb-2">
              🤖 Dual-Agent Pipeline Control
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/60 space-y-2">
                <span className="text-[11px] font-bold text-slate-300 block">Proposer (Fast)</span>
                <select
                  value={proposerProvider}
                  onChange={(e) => setProposerProvider(e.target.value)}
                  className="w-full p-1.5 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200 font-mono"
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="rule">Rule Engine (Fast Fallback)</option>
                </select>
              </div>

              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/60 space-y-2">
                <span className="text-[11px] font-bold text-slate-300 block">Validator (Smart)</span>
                <select
                  value={validatorProvider}
                  onChange={(e) => setValidatorProvider(e.target.value)}
                  className="w-full p-1.5 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200 font-mono"
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="rule">Rule Engine (Fast Fallback)</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleRunDualAgent}
              disabled={evaluating}
              className="w-full py-3 text-xs font-bold uppercase tracking-wider rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all shadow-lg shadow-amber-500/10 font-mono"
            >
              {evaluating ? "⏳ Auditing with 5 Wall St Rules..." : `⚡ Audit Trade (${activeTicker} - ${timeframe})`}
            </button>
          </div>

          {/* Dual Agent Decision Audit Output */}
          {agentResult && (
            <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="uppercase text-slate-400 font-bold">Trader Audit Output</span>
                <span className={`px-2.5 py-1 text-[10px] font-bold uppercase rounded ${
                  agentResult.execution_ready ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                }`}>
                  {agentResult.execution_ready ? "EXECUTION AUTHORIZED" : "REJECTED BY RISK DESK"}
                </span>
              </div>

              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/60 space-y-1">
                <div className="text-[10px] text-amber-400 uppercase font-bold">1. Proposer Trade Proposal</div>
                <div className="text-xs font-bold text-white">Action: {agentResult.proposal?.action}</div>
                <p className="text-[11px] text-slate-400 mt-1">{agentResult.proposal?.reasoning}</p>
              </div>

              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/60 space-y-1">
                <div className="text-[10px] text-emerald-400 uppercase font-bold">2. Validator Wall St Audit</div>
                <div className="text-xs font-bold text-white">Approved: {agentResult.validation?.approved ? "YES" : "NO"}</div>
                <p className="text-[11px] text-slate-400 mt-1">{agentResult.validation?.validation_notes}</p>
              </div>
            </div>
          )}
        </div>

        {/* Full-Width Row (col-span-12): Extended Options Chain Table (SIDE REMOVED, SYMBOL IS JUST TICKER) */}
        <div className="lg:col-span-12">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-xs font-mono uppercase tracking-widest text-amber-400 font-bold">
                Options Chain ({timeframe}) - Click Any Row for Robinhood Contract Detail View
              </h3>
              <span className="text-xs font-mono text-emerald-400 font-bold px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-md">
                {chain.length} Liquid Contracts
              </span>
            </div>
            {/* Desktop Table View (Hidden on Mobile & Tablet) */}
            <div className="hidden lg:block overflow-x-auto max-h-[500px] overflow-y-auto pr-1">
              <table className="w-full font-mono text-xs text-left border-collapse cursor-pointer">
                <thead className="sticky top-0 bg-slate-900 z-10">
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
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
                      <td className="py-2.5 px-3 text-slate-400 font-semibold">{c.expiration}</td>
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
                          className="px-3 py-1 text-[10px] font-bold uppercase rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30 transition-colors font-mono"
                        >
                          View Ticket
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile & Tablet Card List View (Hidden on Desktop) */}
            <div className="block lg:hidden space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {chain.map((c, idx) => (
                <div
                  key={idx}
                  onClick={() => handleOpenContractModal(c)}
                  className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 hover:bg-slate-850 transition-colors flex flex-col gap-2 font-mono text-xs cursor-pointer"
                >
                  <div className="flex justify-between items-center border-b border-slate-850 pb-1.5">
                    <span className="font-black text-amber-400 text-sm">
                      {activeTicker} ${c.strike} {c.type}
                    </span>
                    <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${c.type === "CALL" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border border-rose-500/20"}`}>
                      {c.expiration}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] text-slate-400">
                    <div>Bid / Ask: <span className="text-slate-200 font-semibold">${c.bid} / ${c.ask}</span></div>
                    <div>Midpoint: <span className="text-amber-300 font-bold">${c.midpoint}</span></div>
                    <div>Delta (Δ): <span className="text-emerald-400 font-bold">{c.greeks?.delta}</span></div>
                    <div>Theta (Θ): <span className="text-rose-400">{c.greeks?.theta}</span></div>
                    <div>Vega (V): <span className="text-amber-400">{c.greeks?.vega}</span></div>
                    <div>OI: <span className="text-slate-300">{c.open_interest}</span></div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleOpenContractModal(c);
                    }}
                    className="w-full mt-1.5 py-2 text-center text-[10px] font-bold uppercase rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30 transition-colors"
                  >
                    View Ticket
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>

      {/* Robinhood-Style Contract Detail Modal */}
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

            <div className="space-y-2">
              <span className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">The Greeks & Volatility</span>
              <div className="grid grid-cols-4 gap-2 text-center text-xs">
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[9px] text-slate-400 uppercase font-bold">Delta (Δ)</div>
                  <div className="text-xs font-bold text-emerald-400">{selectedContract.greeks?.delta}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[9px] text-slate-400 uppercase font-bold">Gamma (Γ)</div>
                  <div className="text-xs font-bold text-slate-300">{selectedContract.greeks?.gamma}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[9px] text-slate-400 uppercase font-bold">Theta (Θ)</div>
                  <div className="text-xs font-bold text-rose-400">{selectedContract.greeks?.theta}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[9px] text-slate-400 uppercase font-bold">Vega (V)</div>
                  <div className="text-xs font-bold text-amber-400">{selectedContract.greeks?.vega}</div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs">
              <span className="text-slate-300 font-bold">Estimated Max Cost (100 Shares/Contract):</span>
              <span className="text-base font-black text-amber-400">
                ${(contractQty * (parseFloat(customLimitPrice) || selectedContract.midpoint) * 100).toFixed(2)}
              </span>
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
