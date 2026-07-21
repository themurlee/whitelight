# WhiteLight Systematic Trading & Analysis Pipeline

GHE Url: https://themurlee.github.io/whitelight/

A local-first, risk-constrained systematic options trading pipeline connected to the **Alpaca Trading API** (paper & live execution), complete with a React + Vite control panel and a Streamlit monitoring dashboard.

---

## System Architecture

The WhiteLight pipeline is designed with a modular, local-first, controller-driven architecture.

```mermaid
graph TD
    %% Presentation Layer
    subgraph Presentation [Presentation Layer]
        RUI["React + Vite UI<br>(WhiteLightPanel.jsx)"]
        SDB["Streamlit Dashboard<br>(dashboard.py)"]
    end

    %% Controller Layer
    subgraph Controller [Controller Layer]
        REST["Zero-Dependency API Server<br>(api.py)"]
        PIPE["Core Coordinator Loop<br>(pipeline.py)"]
    end

    %% Analytics & Strategy engines
    subgraph Core [Strategy & Selection Engines]
        SE["Signal Strategy Engine<br>(strategy.py)"]
        SG["Crossover Signal Generator<br>(signal_generator.py)"]
        OS["Options Selector & Structurer<br>(selector.py)"]
    end

    %% Risk & Execution
    subgraph Execution [Risk & Execution Layer]
        CB["Drawdown Circuit Breaker<br>(RiskManager)"]
        EX["Safe Order Routing<br>(execute_order_safely)"]
    end

    %% Data Layer
    subgraph Data [Storage Layer (Local-First)]
        JSON["State & Positions Store<br>(state.json / positions.json)"]
        JL["Transaction Logger & Reflections<br>(trade_log.md / journal/)"]
    end

    %% External
    subgraph External [External Interface]
        Alpaca["Alpaca Trading API<br>(TradingClient / SDK)"]
    end

    %% Relationships
    RUI <-->|REST API / JSON| REST
    SDB <-->|Reads JSON & Logs| Data
    REST <-->|Manages State & Launches| PIPE
    PIPE <-->|Saves/Reads State| Data
    PIPE -->|Verifies Constraints| CB
    PIPE -->|Generates Signals| SE
    PIPE -->|Filters Chain| OS
    PIPE -->|Submits Orders| EX
    EX -->|State Updates| Data
    EX <-->|API Calls| Alpaca
    SG -->|Indicator Calc| SE
    SG -->|Logs Signal| Data
    CB <-->|Alpaca Portfolio Value| Alpaca
```

### Folder Structure

```
whitelight/
├── src/
│   ├── pipeline.py          # Main execution coordinator loop
│   ├── strategy.py          # Pure Python technical indicators (EMA, VWAP, MACD, RSI)
│   ├── selector.py          # Multi-leg defined-risk structure builder (spreads, condors)
│   ├── execution.py         # Alpaca SDK wrapper, RiskManager, and safe routing path
│   ├── backtest.py          # Event-driven backtesting engine with slippage & commission cost models
│   ├── run_backtest.py      # Backtest CLI runner
│   ├── ingest.py            # Alpaca historical bar ingestion engine
│   ├── signal_generator.py  # MACD/RSI signal generation & log generator
│   ├── api.py               # Zero-dependency Python backend REST API server
│   ├── journal.py           # Journal logger and reflection document generator
│   └── dashboard.py         # Streamlit real-time monitoring interface
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React app shell
│   │   ├── WhiteLightPanel.jsx  # Control panel dashboard component
│   │   └── App.css              # Custom styling definitions
│   └── package.json
├── tests/                   # Complete Python unittest suite
├── data/
│   ├── state.json           # Circuit breaker metrics, drawdown state, and manual controls
│   ├── positions.json       # Local records of currently active options contracts
│   └── journal/             # Qualitative reflection markdown logs + trade_log.md
└── .env                     # Local credentials (API key, secret key, environment toggle)
```

---

## Systematic Trading & Option Selection Strategies

WhiteLight utilizes pure-Python implementations of mathematical indicators to eliminate overhead, avoid dependency discrepancies, and guarantee execution determinism.

### 1. Intraday Trend-Following Strategy (`strategy.py`)
This strategy combines macro-trend filters with micro-price location relative to volume-weighted anchors to determine entering directional trades.
*   **Warmup Threshold**: Requires a minimum of 250 historical price bars.
*   **Macro Filter (EMA Golden/Death Cross)**: Calculates the 50-period Exponential Moving Average ($\text{EMA}_{50}$) and the 250-period Exponential Moving Average ($\text{EMA}_{250}$).
    $$\text{EMA}_t = \text{Price}_t \times \alpha + \text{EMA}_{t-1} \times (1 - \alpha), \quad \alpha = \frac{2}{\text{Period} + 1}$$
*   **Intraday Anchor (Session VWAP)**: Session Volume-Weighted Average Price resets dynamically at the start of each daily trading session.
    $$\text{VWAP} = \frac{\sum (\text{Typical Price} \times \text{Volume})}{\sum \text{Volume}}, \quad \text{Typical Price} = \frac{\text{High} + \text{Low} + \text{Close}}{3}$$
*   **Decision Matrix**:
    *   **Bullish Signal**: $\text{EMA}_{50} > \text{EMA}_{250}$ AND $\text{Current Price} > \text{Session VWAP}$. Action: **Acquire Bullish Leg (Call)**.
    *   **Bearish Signal**: $\text{EMA}_{50} < \text{EMA}_{250}$ AND $\text{Current Price} < \text{Session VWAP}$. Action: **Acquire Bearish Leg (Put)**.
    *   **Neutral State**: Any other configuration. Action: **Hold (No Entry)**.

### 2. MACD-RSI Crossover Signal Generator (`signal_generator.py`)
A momentum-reversal strategy that filters MACD trend shifts using an RSI boundary condition to avoid buying overextended breakouts.
*   **MACD Configuration**: 12-period Fast EMA, 26-period Slow EMA, and 9-period Signal Line (EMA of MACD Line).
    $$\text{MACD Line} = \text{EMA}_{12} - \text{EMA}_{26}$$
    $$\text{Signal Line} = \text{EMA}_{9}(\text{MACD Line})$$
    $$\text{Histogram} = \text{MACD Line} - \text{Signal Line}$$
*   **RSI Filter**: Standard 14-period Relative Strength Index using Wilder's smoothing method.
*   **Execution Criteria**:
    *   **BUY Signal**: $\text{MACD Line}$ crosses above the $\text{Signal Line}$ AND current $\text{RSI} < 70$.
    *   **SELL Signal**: $\text{MACD Line}$ crosses below the $\text{Signal Line}$.
    *   **HOLD Signal**: All other states.

### 3. Option Selection & Structuring (`selector.py`)
The pipeline automatically converts directional signals into risk-defined derivatives positions.

*   **Single-Leg Selection**: Finds the closest expiration to **30 Days to Expiration (DTE)** and selects the contract on that date with an absolute delta closest to **0.40 Delta** ($\Delta = 0.40$ for calls, $\Delta = -0.40$ for puts).
*   **Vertical Credit Spreads**:
    *   **Bull Put Spread**: Sells a put at the `target_delta` (default: 0.20) and buys a protective put `width` (default: $5.00) points lower.
    *   **Bear Call Spread**: Sells a call at the `target_delta` (default: 0.20) and buys a protective call `width` (default: $5.00) points higher.
    *   **Liquidity Guard**: Filters out any contract where the bid-ask spread relative to mid-price exceeds `max_spread_pct` (default: 10%).
        $$\text{Spread \%} = \frac{\text{Ask} - \text{Bid}}{\text{Mid}} \le 10\%$$
*   **Iron Condor**:
    *   Constructs a delta-neutral, range-bound 4-leg structure combining a Bull Put Spread and a Bear Call Spread.
    *   **Volatility Filter**: Demands that the underlying's Implied Volatility Rank ($\text{IV Rank}$) is $\ge 45\%$. Low IV conditions automatically reject the trade (bypassed in backtests).

---

## Safety Controls & Risk Management

WhiteLight implements a multi-tier, failsafe risk framework executing checks prior to any order placement.

```
                  [Order Ingest Request]
                            │
              Is manual_pause == true? ───(Yes)───> [Execution Blocked]
                            │ (No)
            Is lockdown_active == true? ──(Yes)───> [Execution Blocked]
                            │ (No)
              Rolling 7D Drawdown >= 15%? ──(Yes)──> [Trigger Emergency Lockdown]
                            │ (No)                       - Cancel all open orders
                            ▼                            - Flatten all positions
                 [Route Order to Alpaca]                 - Set lockdown_active = true
```

### Risk Controls Configuration (`execution.py`)

1.  **Independent Safety Gates**:
    *   `lockdown_active`: Set automatically by the 7D Drawdown circuit breaker. It can **only** be cleared manually by an operator via modifying `state.json` or invoking `POST /api/state/reset`.
    *   `manual_pause`: Toggled manually via the UI control panel.
    *   *Failsafe Constraint*: Neither flag can clear the other. Both must resolve to `false` for any order routing to proceed.
2.  **Rolling 7-Day Drawdown Circuit Breaker**:
    Every execution cycle audits the rolling 7-day equity trajectory:
    1.  Records the peak portfolio equity value observed over the last 7 calendar days.
    2.  Calculates the current drawdown relative to this peak.
        $$\text{Drawdown} = \frac{\text{Peak Equity} - \text{Current Equity}}{\text{Peak Equity}}$$
    3.  If drawdown $\ge 15.00\%$, triggers **Emergency Lockdown**:
        *   Sets `lockdown_active = true` in `data/state.json`.
        *   Purges all pending order tickets via Alpaca `cancel_orders()`.
        *   Immediately closes/flattens all active option contracts to cash.
        *   Locks further automated or manual order entry until cleared.

---

## API Endpoints (`src/api.py`)

The zero-dependency Python REST backend exposes the following interfaces:

| Method | Endpoint | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/state` | None | Returns state variables (`lockdown_active`, `manual_pause`, `equity_history`). |
| **POST** | `/api/state/reset` | None | Reset `lockdown_active` to `false` (does not affect `manual_pause`). |
| **POST** | `/api/state/lockdown` | None | Manually trigger emergency circuit-breaker lockdown. |
| **POST** | `/api/state/manual_pause` | `{"paused": true/false}` | Toggles operator-forced manual execution pause. |
| **POST** | `/api/systematic/ingest` | `{"ticker": "SPY"}` | Ingest and cache historical OHLCV bar data locally. |
| **POST** | `/api/systematic/signal` | `{"ticker": "SPY"}` | Calculate technical indicators and yield current action. |
| **POST** | `/api/systematic/execute` | None | Execute orders for the latest calculated signal via Alpaca. |
| **POST** | `/api/systematic/backtest` | `{"ticker": "SPY", "capital": 100000}` | Run local event-driven backtesting engine. |
| **POST** | `/api/systematic/manual_order` | `{symbol, side, qty, order_type, limit_price?}` | Route operator-initiated order through safety check path. |

---

## Getting Started

### 1. Configure Environment Credentials
Create a `.env` file in the root directory:
```env
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_PAPER=true      # Set false to route to live account (use caution!)
```

### 2. Install Project Dependencies
```bash
pip install alpaca-py pandas numpy
cd frontend && npm install
```

### 3. Run Unit Test Suites
Verify all calculations, selectors, and safety logic match mathematical specifications:
```bash
python3 -m unittest discover -s tests
```
*Expected output: `Ran 44 tests in ~0.04s — OK`*

### 5. Start the Application Stack
Run the Python API server, the Vite React UI, and optionally the Streamlit dashboard:
```bash
# Terminal 1: REST API
python3 src/api.py

# Terminal 2: React Panel UI
cd frontend && npm run dev

# Terminal 3: Streamlit Metrics (Optional)
streamlit run src/dashboard.py
```
