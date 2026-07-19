/**
 * WhiteLightPanel.jsx — 🤖 Systematic Pipeline control center
 *
 * Surfaces:
 *  1. Status bar — Alpaca connection + both flag states (lockdown_active, manual_pause)
 *  2. Data Ingestion Engine
 *  3. Signal Generation & Calculations
 *  4. Manual Order Ticket (checks both flags independently on API)
 *  5. Backtest Runner (uses locally cached OHLCV data)
 *  6. Trade Log Console
 *
 * Props:
 *  state              — { lockdown_active, manual_pause, ... } from /api/state
 *  systematicStatus   — { tickers, account, logs, signal }
 *  onRefreshState     — () => void
 *  onRefreshStatus    — () => void
 */

import React, { useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api';

// ─── colour tokens (matches App.css design system) ──────────────────────────
const C = {
  cyan:    '#00F2FE',
  green:   '#10B981',
  red:     '#EF4444',
  yellow:  '#FBBF24',
  muted:   '#94A3B8',
  blue:    '#38BDF8',
  surface: 'rgba(15, 23, 42, 0.7)',
  card:    'rgba(30, 41, 59, 0.45)',
  border:  'rgba(255,255,255,0.08)',
};

// ─── tiny reusable atoms ────────────────────────────────────────────────────

const Pill = ({ ok, children }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 10px', borderRadius: 20, fontSize: '0.7rem',
    fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
    background: ok ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
    color: ok ? C.green : C.red,
    border: `1px solid ${ok ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`,
  }}>{children}</span>
);

const MiniCard = ({ label, value, color }) => (
  <div style={{
    padding: '10px 12px', borderRadius: 8,
    background: C.card, border: `1px solid ${C.border}`, flex: 1,
  }}>
    <div style={{ fontSize: '0.62rem', color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: color || 'white', marginTop: 3 }}>{value}</div>
  </div>
);

const Block = ({ title, desc, children, style = {} }) => (
  <div className="dashboard-block" style={style}>
    <h2 style={{ margin: '0 0 2px 0' }}>{title}</h2>
    {desc && <p className="block-desc" style={{ marginTop: 0 }}>{desc}</p>}
    {children}
  </div>
);

const LogConsole = ({ text }) => (
  <div style={{
    background: '#020617', border: `1px solid ${C.border}`, borderRadius: 8,
    padding: '10px 12px', fontFamily: 'JetBrains Mono, monospace',
    fontSize: '0.72rem', color: C.green, height: 220, overflowY: 'auto', whiteSpace: 'pre-wrap',
    lineHeight: 1.7,
  }}>
    {text || 'No logs available.'}
  </div>
);


// ─── status bar ─────────────────────────────────────────────────────────────

function StatusBar({ state, systematicStatus, onTogglePause, pauseLoading }) {
  const { lockdown_active = false, manual_pause = false } = state || {};
  const acc = systematicStatus?.account || {};

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
      padding: '10px 16px', borderRadius: 10, marginBottom: 20,
      background: C.card, border: `1px solid ${C.border}`,
    }}>
      {/* Connection */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginRight: 8 }}>
        <span className={`status-dot ${acc.configured && !acc.error ? 'dot-active' : 'dot-inactive'}`} />
        <span style={{ fontSize: '0.78rem', color: C.muted }}>
          {acc.configured && !acc.error
            ? `Alpaca · ${acc.account_number || '—'}`
            : acc.error ? 'Connection error' : 'Not configured'}
        </span>
      </div>

      <div style={{ flex: 1 }} />

      {/* Lockdown flag */}
      <Pill ok={!lockdown_active}>
        {lockdown_active ? '🔴 LOCKDOWN ACTIVE' : '✅ Circuit breaker OK'}
      </Pill>

      {/* Manual pause flag + toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Pill ok={!manual_pause}>
          {manual_pause ? '⏸ MANUAL PAUSE' : '▶ Live execution'}
        </Pill>
        <button
          onClick={onTogglePause}
          disabled={pauseLoading}
          style={{
            padding: '3px 12px', borderRadius: 6, fontSize: '0.72rem',
            fontWeight: 700, cursor: pauseLoading ? 'wait' : 'pointer',
            background: manual_pause ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.12)',
            color: manual_pause ? C.green : C.red,
            border: `1px solid ${manual_pause ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.25)'}`,
          }}
        >
          {pauseLoading ? '…' : manual_pause ? 'Resume' : 'Pause'}
        </button>
      </div>
    </div>
  );
}


// ─── Alpaca account widget ───────────────────────────────────────────────────

function AlpacaBlock({ account }) {
  if (!account) return null;
  const { configured, error, account_number, equity, buying_power, cash } = account;
  const fmt = (n) => n?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <Block title="💳 Alpaca Connection" desc="Real-time paper trading account status">
      {!configured ? (
        <div style={{ padding: 14, borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5', fontSize: '0.85rem' }}>
          <strong>Not Configured</strong>
          <p style={{ margin: '6px 0 0' }}>Create a <code>.env</code> file with ALPACA_API_KEY and ALPACA_SECRET_KEY.</p>
        </div>
      ) : error ? (
        <div style={{ padding: 14, borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5', fontSize: '0.85rem' }}>
          <strong>Connection Error</strong>
          <p style={{ margin: '6px 0 0' }}>{error}</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: '#86EFAC', fontSize: '0.82rem' }}>
            <span className="status-dot dot-active" />
            Paper account · {account_number}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <MiniCard label="Portfolio Equity" value={`$${fmt(equity)}`} color={C.blue} />
            <MiniCard label="Buying Power"     value={`$${fmt(buying_power)}`} color={C.blue} />
          </div>
          <div style={{ fontSize: '0.78rem', color: C.muted }}>
            Cash: <strong style={{ color: 'white' }}>${fmt(cash)}</strong>
          </div>
        </div>
      )}
    </Block>
  );
}


// ─── signal display widget ───────────────────────────────────────────────────

function SignalCard({ signal, onExecute, executingLoading }) {
  if (!signal) return (
    <div className="metric-card">
      <p className="text-muted">No active signal loaded. Calculate a signal above.</p>
    </div>
  );

  const actionColor = signal.action === 'BUY' ? C.green : signal.action === 'SELL' ? C.red : C.muted;

  return (
    <div className="metric-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: '1.1rem', color: C.cyan }}>{signal.ticker} Signal</span>
        <span style={{ fontSize: '0.7rem', color: C.muted }}>{signal.timestamp}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <MiniCard label="Close"     value={`$${signal.close}`} />
        <MiniCard label="RSI (14)"  value={signal.rsi}  color={signal.rsi > 70 ? C.red : signal.rsi < 30 ? C.green : 'white'} />
        <MiniCard label="MACD Hist" value={signal.macd_histogram} color={signal.macd_histogram > 0 ? C.green : C.red} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)', padding: '12px 14px', borderRadius: 8, border: `1px solid ${C.border}` }}>
        <div>
          <div style={{ fontSize: '0.65rem', color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Recommendation</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: actionColor }}>{signal.action}</div>
        </div>
        <button
          onClick={onExecute}
          className="form-submit-btn"
          disabled={executingLoading || signal.action === 'HOLD'}
          style={{ margin: 0, padding: '8px 18px', background: actionColor, color: 'black', cursor: signal.action === 'HOLD' ? 'not-allowed' : 'pointer', opacity: signal.action === 'HOLD' ? 0.4 : 1 }}
        >
          {executingLoading ? 'Executing…' : `Execute ${signal.action}`}
        </button>
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
  const retColor = m.total_return_pct > 0 ? C.green : C.red;

  return (
    <Block title="📈 Backtest Runner" desc="EMA50/EMA250/VWAP strategy on locally cached OHLCV — no live data call needed">
      <form onSubmit={run} className="weekly-review-form" style={{ marginBottom: 16 }}>
        <div className="form-row" style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 2, marginBottom: 0 }}>
            <label>Ticker (must be ingested first)</label>
            <input type="text" placeholder="SPY" value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} required style={{ width: '100%' }} />
          </div>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label>Initial Capital ($)</label>
            <input type="number" min="1000" step="1000" value={capital} onChange={e => setCapital(e.target.value)} style={{ width: '100%' }} />
          </div>
          <button type="submit" className="form-submit-btn" disabled={loading} style={{ margin: 0, padding: '12px 20px', whiteSpace: 'nowrap' }}>
            {loading ? 'Running…' : '▶ Run Backtest'}
          </button>
        </div>
      </form>

      {error && <div style={{ color: C.red, fontSize: '0.82rem', marginBottom: 10 }}>⚠ {error}</div>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <MiniCard label="Total Return"  value={`${m.total_return_pct > 0 ? '+' : ''}${m.total_return_pct}%`} color={retColor} />
            <MiniCard label="Sharpe Ratio"  value={m.sharpe ?? '—'} color={m.sharpe > 1 ? C.green : C.muted} />
            <MiniCard label="Max Drawdown"  value={`-${m.max_drawdown_pct}%`} color={C.red} />
            <MiniCard label="# Trades"      value={m.num_trades} />
            <MiniCard label="Final Equity"  value={`$${m.final_equity?.toLocaleString()}`} color={C.blue} />
          </div>
          <details>
            <summary style={{ cursor: 'pointer', fontSize: '0.78rem', color: C.muted }}>Full summary ▸</summary>
            <pre style={{ fontSize: '0.72rem', color: C.muted, marginTop: 8, whiteSpace: 'pre-wrap' }}>{result.summary}</pre>
          </details>
        </div>
      )}
    </Block>
  );
}


// ─── manual order ticket ─────────────────────────────────────────────────────

function ManualOrderTicket({ state }) {
  const [symbol, setSymbol]         = useState('');
  const [side, setSide]             = useState('buy');
  const [qty, setQty]               = useState(1);
  const [orderType, setOrderType]   = useState('market');
  const [limitPrice, setLimitPrice] = useState('');
  const [loading, setLoading]       = useState(false);
  const [result, setResult]         = useState(null);
  const [error, setError]           = useState('');

  const isBlocked = state?.lockdown_active || state?.manual_pause;

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setResult(null); setError('');
    try {
      const body = { symbol: symbol.toUpperCase(), side, qty: parseInt(qty), order_type: orderType };
      if (orderType === 'limit' && limitPrice) body.limit_price = parseFloat(limitPrice);
      const res = await fetch(`${API_BASE}/systematic/manual_order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.success) setResult(data.order);
      else setError(data.error || 'Order failed.');
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Block
      title="🎯 Manual Order Ticket"
      desc="Operator-initiated order — same risk checks as automated pipeline (both flags must be clear)"
    >
      {isBlocked && (
        <div style={{ padding: '10px 14px', borderRadius: 8, marginBottom: 14, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', fontSize: '0.8rem', color: '#FCA5A5' }}>
          ⚠ {state?.lockdown_active ? 'Circuit breaker lockdown is active.' : 'Manual pause is active.'} Orders will be rejected by the API.
        </div>
      )}

      <form onSubmit={submit} className="weekly-review-form">
        <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Symbol</label>
            <input type="text" placeholder="e.g. SPY, AAPL260814C00185000" value={symbol} onChange={e => setSymbol(e.target.value)} required />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Side</label>
            <select value={side} onChange={e => setSide(e.target.value)} style={{ width: '100%' }}>
              <option value="buy">BUY</option>
              <option value="sell">SELL</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Qty</label>
            <input type="number" min="1" value={qty} onChange={e => setQty(e.target.value)} />
          </div>
        </div>
        <div className="form-row" style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Order Type</label>
            <select value={orderType} onChange={e => setOrderType(e.target.value)}>
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>
          {orderType === 'limit' && (
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Limit Price</label>
              <input type="number" min="0.01" step="0.01" value={limitPrice} onChange={e => setLimitPrice(e.target.value)} required={orderType === 'limit'} />
            </div>
          )}
          <button type="submit" className="form-submit-btn" disabled={loading} style={{ margin: 0 }}>
            {loading ? 'Submitting…' : 'Submit Order'}
          </button>
        </div>
      </form>

      {error && <div style={{ color: C.red, fontSize: '0.82rem', marginTop: 10 }}>⚠ {error}</div>}
      {result && (
        <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', fontSize: '0.82rem', color: '#86EFAC' }}>
          ✅ Order placed · ID: <code>{result.order_id}</code> · Status: {result.status}
        </div>
      )}
    </Block>
  );
}


// ─── main panel ─────────────────────────────────────────────────────────────

export default function AlpacaPanel({
  state,
  systematicStatus,
  onRefreshState,
  onRefreshStatus,
  // passthrough handlers from App.jsx
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
  const [pauseLoading, setPauseLoading] = useState(false);

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

  return (
    <div>
      {/* ── Status bar ── */}
      <StatusBar
        state={state}
        systematicStatus={systematicStatus}
        onTogglePause={handleTogglePause}
        pauseLoading={pauseLoading}
      />

      <div className="panel-grid">
        {/* ── Left column ── */}
        <div className="grid-col-2">
          {/* 1. Ingest */}
          <Block title="🤖 Data Ingestion Engine" desc="Fetch and backfill daily OHLCV bars via Alpaca-py IEX feed">
            <form onSubmit={handleIngestSubmit} className="weekly-review-form" style={{ marginBottom: 20 }}>
              <div className="form-row" style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label>Symbol / Ticker</label>
                  <input type="text" placeholder="e.g. SPY, AAPL, MSFT" value={ingestTicker} onChange={e => setIngestTicker(e.target.value.toUpperCase())} required style={{ width: '100%' }} />
                </div>
                <button type="submit" className="form-submit-btn" disabled={ingestLoading} style={{ margin: 0, padding: '12px 20px', whiteSpace: 'nowrap' }}>
                  {ingestLoading ? 'Ingesting…' : 'Ingest OHLCV'}
                </button>
              </div>
            </form>

            <h3 style={{ margin: '0 0 8px' }}>Ingested Datasets</h3>
            {Object.keys(systematicStatus.tickers).length === 0 ? (
              <p className="text-muted">No local data found. Ingest a ticker above.</p>
            ) : (
              <div className="table-responsive">
                <table className="kinfo-table">
                  <thead>
                    <tr>
                      <th>Ticker</th><th>Daily Bars</th><th>History Range</th><th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(systematicStatus.tickers).map(([ticker, info]) => (
                      <tr key={ticker}>
                        <td style={{ fontWeight: 700, color: C.cyan }}>{ticker}</td>
                        <td>{info.count}</td>
                        <td>{info.first_date && info.last_date ? `${info.first_date} → ${info.last_date}` : 'N/A'}</td>
                        <td>Alpaca IEX</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Block>

          {/* 2. Signal generation */}
          <Block title="📊 Signal Generation & Calculations" desc="EMA50/EMA250/VWAP-based systematic signal engine" style={{ marginTop: 20 }}>
            <form onSubmit={handleGenerateSignal} className="weekly-review-form" style={{ marginBottom: 20 }}>
              <div className="form-row" style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label>Calculate Signal for Ticker</label>
                  <input type="text" placeholder="e.g. SPY" value={signalTicker} onChange={e => setSignalTicker(e.target.value.toUpperCase())} required style={{ width: '100%' }} />
                </div>
                <button type="submit" className="form-submit-btn" disabled={signalLoading} style={{ margin: 0, padding: '12px 20px', whiteSpace: 'nowrap' }}>
                  {signalLoading ? 'Calculating…' : 'Run Indicator Calc'}
                </button>
              </div>
            </form>

            <SignalCard
              signal={systematicStatus.signal}
              onExecute={handleExecuteSignal}
              executingLoading={executingLoading}
            />
          </Block>

          {/* 3. Backtest runner */}
          <div style={{ marginTop: 20 }}>
            <BacktestRunner />
          </div>
        </div>

        {/* ── Right sidebar ── */}
        <div className="grid-sidebar">
          {/* 4. Alpaca account */}
          <AlpacaBlock account={systematicStatus.account} />

          {/* 5. Manual order ticket */}
          <div style={{ marginTop: 20 }}>
            <ManualOrderTicket state={state} />
          </div>

          {/* 6. Trade log */}
          <Block title="📜 Trade Log Console" desc="Last 100 lines from data/journal/trade_log.md" style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <button
                onClick={fetchSystematicStatus}
                className="nav-item"
                style={{ fontSize: '0.78rem', padding: '4px 10px', margin: 0, height: 'auto', background: 'rgba(255,255,255,0.05)' }}
              >
                🔄 Refresh
              </button>
            </div>
            <LogConsole text={systematicStatus.logs} />
          </Block>
        </div>
      </div>
    </div>
  );
}
