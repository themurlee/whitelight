# WhiteLight Systematic Trading & Analysis Pipeline

GHE Url: https://themurlee.github.io/whitelight/

A local-first, risk-constrained systematic options trading pipeline connected to **Alpaca Trading API** (paper & live), with a React + Vite browser UI and a Streamlit monitoring dashboard.

---

## System Architecture

```
whitelight/
├── src/
│   ├── pipeline.py          # Main execution coordinator loop
│   ├── strategy.py          # EMA50/EMA250/session VWAP signal engine + systematic_strategy()
│   ├── selector.py          # Options chain filter (30 DTE / 0.40Δ) + vertical_credit_spread + iron_condor
│   ├── execution.py         # Alpaca SDK client, 7D drawdown circuit breaker, manual_pause flag
│   ├── backtest.py          # Event-driven backtesting engine with cost model + metrics
│   ├── run_backtest.py      # CLI: python3 src/run_backtest.py --ticker SPY --start 2022-01-01 --end 2025-01-01
│   ├── ingest.py            # Alpaca IEX historical OHLCV fetcher (StockHistoricalDataClient)
│   ├── signal_generator.py  # RSI(14) / MACD(12,26,9) indicators
│   ├── api.py               # Zero-dependency HTTP REST server (backend for React UI)
│   ├── journal.py           # JSON transaction logger & MD journal generator
│   └── dashboard.py         # Streamlit monitoring dashboard
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Root app — Options journal tab + Systematic Pipeline tab
│   │   ├── WhiteLightPanel.jsx  # 🤖 Systematic Pipeline control center component
│   │   └── App.css              # Design system (dark theme, tokens, utilities)
│   └── package.json
├── tests/                   # Unit test suites (44 tests, python3 -m unittest discover -s tests)
├── data/
│   ├── state.json           # lockdown_active, manual_pause, equity_history
│   ├── positions.json       # Active options positions
│   └── journal/             # Qualitative markdown logs + trade_log.md
└── .env                     # ALPACA_API_KEY, ALPACA_SECRET_KEY (never committed)
```

---

## Getting Started

### 1. Credentials

Create a `.env` file in the project root:
```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true      # omit or set false for live trading
```

### 2. Install dependencies
```bash
pip install alpaca-py pandas numpy
cd frontend && npm install
```

### 3. Run unit tests
```bash
python3 -m unittest discover -s tests
# Expected: Ran 44 tests in ~0.04s — OK
```

### 4. Run the pipeline (dry-run / live)
```bash
# Dry-run (simulation, no real orders)
python3 src/pipeline.py --ticker AAPL

# Live Alpaca mode (paper account, credentials required)
python3 src/pipeline.py --ticker AAPL --live
```

### 5. Start the backend API server
```bash
python3 src/api.py
# Listens on http://127.0.0.1:8000
```

### 6. Start the React UI
```bash
cd frontend && npm run dev
# Opens http://localhost:5173
```

### 7. Run the backtester (CLI)
```bash
# Uses Alpaca to fetch bars and runs systematic_strategy
python3 src/run_backtest.py --ticker SPY --start 2022-01-01 --end 2025-01-01
python3 src/run_backtest.py --ticker AAPL --start 2023-01-01 --end 2024-01-01 --capital 50000

# Or run against locally cached data via the UI Backtest Runner
# (ingest the ticker first via the Data Ingestion Engine block)
```

### 8. Streamlit dashboard (optional)
```bash
streamlit run src/dashboard.py
```

---

## Core Systems & Safety Constraints

### Risk Management — Two Independent Flags

Two flags in `data/state.json` gate all order execution. They are **completely independent** — neither one clears the other.

| Flag | Set by | Cleared by | Effect |
|------|--------|------------|--------|
| `lockdown_active` | Automatic circuit breaker (7D/15% drawdown) | Manual operator action in state.json or API `POST /api/state/reset` | Purges all orders + flattens positions |
| `manual_pause` | Operator via UI toggle or `POST /api/state/manual_pause` | Operator only | Blocks execution without any position change |

Both flags are checked before any order submission (automated **and** manual orders).

### Circuit Breaker — Rolling 7-Day / 15% Drawdown
Every execution cycle audits the rolling 7-day equity history:
1. Calculates peak equity over the last 7 days.
2. Compares peak against current Alpaca portfolio value.
3. If drawdown ≥ **15%**, triggers emergency lockdown:
   - Sets `lockdown_active = true` in `data/state.json`.
   - Purges all pending orders via Alpaca `cancel_orders()`.
   - Flattens all active options positions to cash.
   - Blocks all further execution until lockdown is manually cleared.
   - `manual_pause` is **NOT** modified by this process.

### Options Selector — Defined-Risk Structures
`src/selector.py` supports three structures:

| Function | Description |
|----------|-------------|
| `filter_options_chain()` | Single-leg: closest DTE + delta match |
| `vertical_credit_spread()` | Bull put or bear call spread, with liquidity filter (bid/ask spread %) |
| `iron_condor()` | 4-leg condor with IV rank filter (`min_iv_rank=45` default, pass `iv_rank=None` to bypass in backtests) |

### Backtesting Engine (`src/backtest.py`)
- Event-driven simulation iterating bar-by-bar
- `CostModel` applies commission + slippage in bps
- `BacktestResult.summary()` returns total return, Sharpe ratio, max drawdown, trade count
- `systematic_strategy()` in `src/strategy.py` implements EMA50/EMA250/VWAP signal with 250-bar warmup
- CLI: `python3 src/run_backtest.py`
- API: `POST /api/systematic/backtest` (uses locally cached OHLCV, no Alpaca call)

### REST API Endpoints (src/api.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/state` | Returns full system state including both flags |
| POST | `/api/state/reset` | Clear `lockdown_active` (does NOT touch `manual_pause`) |
| POST | `/api/state/lockdown` | Manually trigger lockdown |
| POST | `/api/state/manual_pause` | Body: `{"paused": true/false}` — toggle operator pause |
| POST | `/api/systematic/ingest` | Body: `{"ticker": "SPY"}` — fetch & cache OHLCV |
| POST | `/api/systematic/signal` | Body: `{"ticker": "SPY"}` — run indicator calc |
| POST | `/api/systematic/execute` | Execute most recent signal via Alpaca |
| POST | `/api/systematic/backtest` | Body: `{"ticker": "SPY", "capital": 100000}` — run backtest |
| POST | `/api/systematic/manual_order` | Body: `{symbol, side, qty, order_type, limit_price?}` — operator order |

### Local-First Data Schema
- **Positions**: `data/positions.json`
- **System State**: `data/state.json` — `lockdown_active`, `manual_pause`, `drawdown_locked_at`, `equity_history`
- **Trading Journal**: Auto-created at `data/journal/YYYY-MM-DD_reflection.md`
- **Trade Log**: `data/journal/trade_log.md`

---

## UI — Two Distinct Surfaces

| Tab | Purpose | Schema |
|-----|---------|--------|
| **Options** | Manual trade journal — log, review, annotate real trades | **Read-only schema** — fields never change |
| **🤖 Systematic Pipeline** | Automated Alpaca-connected control center (`WhiteLightPanel.jsx`) | Live data from API |

The Options tab schema and all its existing data are **never modified** by any Systematic Pipeline changes.
