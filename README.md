# WhiteLight Systematic Trading & Analysis Pipeline

A local-first, risk-constrained systematic options trading pipeline integrated with a Robinhood Model Context Protocol (MCP) server interface and Streamlit monitoring dashboard.

## System Architecture

```
WhiteLight-Systematic-Workspace/
├── src/
│   ├── strategy.py      # Mathematical indicator core (EMA, MACD, session VWAP)
│   ├── selector.py      # Options chain filter (targets 30 DTE, 0.40 Delta)
│   ├── execution.py     # MCP client routing and 7D drawdown circuit breaker
│   ├── journal.py       # JSON transaction logger & MD journal generator
│   └── dashboard.py     # Local Streamlit UI dashboard
├── data/                # Local database engines (Flat files)
│   ├── state.json       # System configuration, flags, and equity history
│   ├── positions.json   # Log of active portfolio positions
│   └── journal/         # Human qualitative markdown logs
└── tests/               # Test suites utilizing mock market datasets
```

---

## Getting Started

### 1. Installation
Install the required packages (`streamlit`, `pandas`):
```bash
pip install streamlit pandas
```

### 2. Run the Unit Tests
Verify all mathematical indicators, filtering rules, circuit breakers, and logging systems are functional before running the pipeline:
```bash
python3 -m unittest discover -s tests
```

### 3. Executing the Pipeline Cycle
Run the coordinator script to audit risk metrics, calculate trend signals, filter option chains, and submit orders.
- **Dry-run (Simulation Mode, default)**:
  ```bash
  python3 src/pipeline.py --ticker AAPL
  ```
- **Live MCP Mode** (requires Robinhood MCP server configuration):
  ```bash
  python3 src/pipeline.py --ticker AAPL --live
  ```

### 4. Running the Dashboard
Launch the premium dark-themed Streamlit user interface to monitor the system:
```bash
streamlit run src/dashboard.py
```

---

## Core Systems & Safety Constraints

### Risk Management Circuit Breaker
Every execution cycle (and every 15 minutes in a live environment), the risk module audits the rolling 7-day equity history:
1. Calculates the peak equity over the last 7 days.
2. Compares the peak equity against the current portfolio valuation.
3. If a drawdown exceeding **15%** is detected, it triggers the circuit breaker:
   - Sets `lockdown_active = true` in `data/state.json`.
   - Purges all active and working orders via MCP.
   - Submits opposing market orders to flatten (sell to cash) all active options positions in `data/positions.json`.
   - Disallows any further order execution until lockdown state is manually cleared.

### Local-First Data Schema
- **Positions**: Tracked under [positions.json](file:///Users/bmurali/WhiteLight-Systematic-Workspace/data/positions.json).
- **System State**: Tracked under [state.json](file:///Users/bmurali/WhiteLight-Systematic-Workspace/data/state.json).
- **Trading Journal**: Qualitative templates are automatically created under `data/journal/YYYY-MM-DD_reflection.md` for manual narrative entries.
