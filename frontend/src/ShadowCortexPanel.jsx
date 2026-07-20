import React, { useState, useEffect } from "react";

/*
  WHITELIGHT — 🧠 SHADOW CORTEX DECISION ENGINE TAB
  Modern Dark UI System with SSE Streaming & MCP Agent Controls
*/

const API_BASE = "http://127.0.0.1:8000/api";

export default function ShadowCortexPanel() {
  const [sseConnected, setSseConnected] = useState(true);
  const [activeProfile, setActiveProfile] = useState("safe_defaults");
  const [deciderModel, setDeciderModel] = useState("gemini-3.5-flash"); // Gemini 3.5 Flash (Low Cost)
  const [callsToday, setCallsToday] = useState(42);
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(500);
  const [cooldownSecs, setCooldownSecs] = useState(18);
  const [mcpActive, setMcpActive] = useState(true);
  const [showProfileDiff, setShowProfileDiff] = useState(false);

  // Sample Audit Stream Events
  const [auditEvents, setAuditEvents] = useState([
    {
      time: "13:01:10 PM",
      type: "PROPOSAL_VALIDATED",
      level: "success",
      title: "PROPOSAL AUTHORIZED: AAPL $230 CALL",
      notes: "Passed 5 Wall St Rules | Midpoint: $9.46 | IV Rank: 32% | OI: 1,450",
      validator: "Gemini 3.5 Flash (Low)"
    },
    {
      time: "13:00:45 PM",
      type: "RISK_GATE_REFUSAL",
      level: "danger",
      title: "ENTRY SKIPPED: NVDA $125 CALL",
      notes: "Refused by Risk Desk — IV Rank 62.4% exceeds 50% cap (IV Crush Hazard)",
      validator: "Gemini 3.5 Flash (Low)"
    },
    {
      time: "12:58:20 PM",
      type: "ORDER_FILLED",
      level: "info",
      title: "PAPER ORDER FILLED: TSLA $240 PUT",
      notes: "Limit Price: $5.10 | Qty: 1 | Broker: Alpaca Paper",
      validator: "System Execution Gate"
    },
    {
      time: "12:55:00 PM",
      type: "HIGH_WATER_MARK_UPDATE",
      level: "warning",
      title: "HIGH-WATER MARK ADJUSTED: MSFT $440 CALL",
      notes: "Peak High: $13.50 | Trailing Stop Locked at $12.15 (+8.2% Profit)",
      validator: "Management Loop"
    }
  ]);

  // Active Positions with High-Water Marks
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

  // Cooldown timer loop simulation
  useEffect(() => {
    const timer = setInterval(() => {
      setCooldownSecs((prev) => (prev > 1 ? prev - 1 : 30));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleSimulateSignal = () => {
    const newEvent = {
      time: new Date().toLocaleTimeString(),
      type: "PROPOSAL_VALIDATED",
      level: "success",
      title: `PROPOSAL AUTHORIZED: SPY $550 CALL`,
      notes: `Passed 5 Wall St Rules | Midpoint: $2.15 | IV Rank: 24% | OI: 8,500`,
      validator: "Gemini 3.5 Flash (Low)"
    };
    setAuditEvents((prev) => [newEvent, ...prev]);
    setCallsToday((prev) => prev + 1);
  };

  return (
    <div className="p-4 space-y-6 text-slate-100 font-sans relative" style={{ background: "#0b0e11", minHeight: "100vh" }}>
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur font-mono">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🧠</span>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-amber-400">Shadow Cortex Decision Engine</h1>
            <p className="text-[10px] text-slate-400">Self-Hosted Event-Driven Trading & MCP Spine</p>
          </div>
        </div>

        {/* SSE & MCP Connection Status */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            ● SSE Stream Connected
          </span>

          <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 flex items-center gap-1.5 font-bold">
            🟢 Claude Desktop MCP Active
          </span>

          {/* Profile Switcher */}
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
        </div>
      </div>

      {/* AI Budget & Intake Cooldown Control Banner */}
      <div className="p-4 rounded-xl border border-amber-500/30 bg-slate-900/40 backdrop-blur font-mono text-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">AI Decider Model</span>
            <span className="font-bold text-emerald-400 text-xs">⚡ Gemini 3.5 Flash (Low Cost)</span>
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
          <div className="text-right">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Batch Cooldown Window</span>
            <span className="font-bold text-amber-400 text-xs">⏳ {cooldownSecs}s until next batch</span>
          </div>

          <button
            onClick={handleSimulateSignal}
            className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all shadow-md shadow-amber-500/10"
          >
            ⚡ Test Intake Signal
          </button>
        </div>
      </div>

      {/* Top KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">💳 System Equity</span>
          <div className="text-xl font-black text-amber-400 font-mono">$100,254.00</div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">📈 Active Positions P&L</span>
          <div className="text-xl font-black text-emerald-400 font-mono">+$254.00 (+12.4%)</div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">🛡️ Risk Desk Pass Rate</span>
          <div className="text-xl font-black text-emerald-400 font-mono">82.5% Passed</div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">🔌 Active MCP Tools</span>
          <div className="text-xl font-black text-indigo-400 font-mono">14 Tools Registered</div>
        </div>
      </div>

      {/* Main Grid: Active Positions Left / Live Audit Feed Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column (col-span-7): Active Positions & High-Water Mark Trailing Stops */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-amber-400 text-base">📈</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  Active Positions & High-Water Mark Trailing Stop Manager
                </h3>
              </div>
              <span className="text-xs text-slate-400 font-bold">{positions.length} Active Positions</span>
            </div>

            <div className="space-y-3">
              {positions.map((pos, idx) => (
                <div key={idx} className="p-4 rounded-xl border border-slate-800 bg-slate-950/70 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-black text-amber-400">{pos.ticker}</span>
                      <span className="text-xs font-bold text-white">${pos.strike} {pos.type}</span>
                      <span className="text-[10px] text-slate-400">Exp: {pos.exp}</span>
                    </div>
                    <span className="text-xs font-black text-emerald-400">+${pos.pnl.toFixed(2)} (+{pos.pnlPct}%)</span>
                  </div>

                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-[9px] text-slate-400 block uppercase">Entry Price</span>
                      <span className="font-bold text-slate-200">${pos.entryPrice}</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-[9px] text-slate-400 block uppercase">Current Price</span>
                      <span className="font-bold text-amber-300">${pos.currentPrice}</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-emerald-500/30">
                      <span className="text-[9px] text-emerald-400 block uppercase font-bold">Peak High</span>
                      <span className="font-black text-emerald-400">${pos.highWaterMark}</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-amber-500/30">
                      <span className="text-[9px] text-amber-400 block uppercase font-bold">Trailing Stop</span>
                      <span className="font-black text-amber-400">${pos.trailingStop}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column (col-span-5): Real-Time Dual-Agent SSE Risk Audit Feed */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-base">📜</span>
                <h3 className="font-bold text-amber-400 uppercase tracking-wider text-xs">
                  Live Audit JSONL Event Stream
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                Auto-Updating (SSE)
              </span>
            </div>

            <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
              {auditEvents.map((evt, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs space-y-1 transition-all ${
                    evt.level === "success"
                      ? "border-emerald-500/30 bg-emerald-500/5"
                      : evt.level === "danger"
                      ? "border-rose-500/30 bg-rose-500/5"
                      : evt.level === "warning"
                      ? "border-amber-500/30 bg-amber-500/5"
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

      </div>

    </div>
  );
}
