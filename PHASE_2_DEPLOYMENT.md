# Phase 2 Deployment: Shadow Strategy B Bridge

**Status**: ✅ **IMPLEMENTATION COMPLETE & READY FOR VALIDATION**  
**Date**: 2026-07-23  
**Integration**: Fully integrated with Phase 1 DualLedgerWriter + Nightly Grader

---

## What Is Phase 2?

Phase 2 transforms WhiteLight from a **single-strategy trader** (Phase 1) into a **20-strategy executor** by bridging Shadow's Strategy B research output directly to Alpaca options trading.

**Architecture**: Shadow strategies → signal generation → contract selection → multi-leg execution → position monitoring → rule-based exits → dual-ledger recording

---

## Components Summary

### 1. **Strategy Registry** (`src/strategies/shadow_bridge/strategy_registry.py`)
- Loads all 20 Shadow Strategy B strategies
- Caches strategies in memory with metadata
- Provides fast lookup, enable/disable control, and status tracking

**Key Classes**:
- `StrategyRegistry`: In-memory cache with load/scan/enable/disable methods

### 2. **Market Data Adapter** (`src/strategies/shadow_bridge/market_data_adapter.py`)
- Fetches live stock quotes from Alpaca
- Provides options chain queries
- Adapter for both Alpaca and Tradier broker data

**Key Classes**:
- `AlpacaTradierAdapter`: Bridge to Alpaca trading API

### 3. **Contract Selector Bridge** (`src/strategies/shadow_bridge/contract_selector.py`)
- Maps Shadow's abstract combos to real Alpaca options contracts
- Finds best contracts by strike, expiry, liquidity, Greeks
- Supports spreads, single legs, multi-leg combos

**Key Classes**:
- `ContractSelectorBridge`: Contract selection + chain fetching

### 4. **Greeks Calculator** (`src/strategies/shadow_bridge/greeks_calculator.py`)
- Calculates Greeks for options combos
- Aggregates delta/gamma/vega/theta across legs
- Risk quantification for position monitoring

**Key Classes**:
- `GreeksCalculatorBridge`: Greeks calculations for combos

### 5. **Exit Rules Engine** (`src/strategies/shadow_bridge/exit_rules_engine.py`)
- Monitors all 13 exit rules per position
- Rule firing: profit target, theta decay, earnings blackout, macro prints, vega collapse, gamma risk, technical breakdown, DTE, calendar vega, correlation, margin, voluntary, max loss
- Urgency classification: CRITICAL, HIGH, MEDIUM, LOW

**Key Classes**:
- `Position`: Position state (combo, Greeks, capital at risk)
- `ExitRulesEngine`: Rule monitoring and enforcement

### 6. **Phase 2 Coordinator** (`src/phase2_coordinator.py`)
- **Main orchestrator** tying all components together
- Pipeline: load strategies → scan → select contracts → calculate Greeks → check circuit breaker → execute legs → dual-write → register position
- Supports dry-run mode, multi-symbol scans, strategy filtering
- **FULLY INTEGRATED WITH PHASE 1**: Calls `DualLedgerWriter.write_execution()` for every trade

**Key Functions**:
- `run_phase2_pipeline()`: Main entry point

### 7. **Test Suite** (`tests/test_phase2_full_bridge.py`)
- Comprehensive tests for all components
- Mock fixtures for Alpaca client
- Integration tests for full pipeline

---

## How It Works: Full Data Flow

```
1. STRATEGY LOADING
   StrategyRegistry.load_all_strategies()
   → Load 20 Shadow strategies from strategies.json
   → Cache in memory
   
2. MARKET DATA FETCH
   AlpacaTradierAdapter.get_quotes(tickers)
   → Fetch live stock prices + IV rank
   
3. STRATEGY SCAN
   StrategyRegistry.scan_all_strategies(market_data)
   → Run entry rules on each strategy
   → Generate signals with confidence
   
4. SIGNAL FILTERING
   Filter → ENTRY signals only
   Sort by confidence (highest first)
   
5. FOR EACH ENTRY SIGNAL:
   
   a) CONTRACT SELECTION
      ContractSelectorBridge.select_contracts()
      → Map abstract combo to Alpaca contracts
      → Find best matches by liquidity + Greeks
      
   b) GREEKS CALCULATION
      GreeksCalculatorBridge.calculate_combo_greeks()
      → Aggregate delta/gamma/vega/theta
      
   c) CIRCUIT BREAKER
      CircuitBreaker.can_execute()
      → Check drawdown, position size, correlation, margin
      
   d) MULTI-LEG EXECUTION
      execute_signal_with_slippage_control() [for each leg]
      → Place limit orders with slippage validation
      → Collect filled legs
      
   e) DUAL-LEDGER WRITE (PHASE 1 INTEGRATION)
      DualLedgerWriter.write_execution()
      → Atomically update state.json (positions)
      → Append to entries.jsonl (Shadow format)
      
   f) POSITION REGISTRATION
      ExitRulesEngine.register_position()
      → Monitor against 13-rule ladder
      
6. NIGHTLY GRADING (PHASE 1)
   ShadowGraderWrapper.grade_whitelight_strategy()
   → Load entries.jsonl
   → Compute e-process wealth
   → Save scorecard.json
```

---

## Deployment: Quick Start

### Step 1: Verify Components
```bash
cd /Users/nekanyab/murlee/whitelight

# Check all files exist
ls -lah src/strategies/shadow_bridge/
ls -lah src/phase2_coordinator.py
ls -lah tests/test_phase2_full_bridge.py
```

### Step 2: Verify Integration with Phase 1
```bash
# Check that phase2_coordinator imports and uses DualLedgerWriter
grep -n "DualLedgerWriter" src/phase2_coordinator.py
grep -n "write_execution" src/phase2_coordinator.py

# Expected: Lines 16 (import) and 215 (call site)
```

### Step 3: Dry-Run on Staging (Paper Account)
```bash
# Run without actual execution
python3 -m src.phase2_coordinator SPY QQQ --dry-run

# Expected output:
# - Loads strategies
# - Scans for signals
# - Selects contracts
# - [DRY RUN] Would execute...
# - No actual orders placed
```

### Step 4: Live Test on Paper Account
```bash
# Real execution on paper account (no actual money)
python3 -m src.phase2_coordinator SPY --dry-run=false

# Monitor:
# 1. Alpaca paper account for filled orders
# 2. data/state.json for active_positions array
# 3. data/entries.jsonl for dual-write records
# 4. Slack alerts for execution events
```

### Step 5: Validate Nightly Grading Integration
```bash
# After positions have been held for a day, run nightly grader
python3 -m src.integration.nightly_grader_task

# Expected:
# - Loads entries.jsonl (includes Phase 2 trades)
# - Computes e-process wealth (worst-fill model)
# - Saves scorecard.json
# - Posts Slack alert with verdict
```

---

## Configuration

Add to `src/config.py` or set as environment variables:

```python
# Phase 2 toggles
PHASE2_ENABLED = os.getenv("PHASE2_ENABLED", "false").lower() == "true"
MAX_POSITIONS_CONCURRENT = int(os.getenv("MAX_POSITIONS_CONCURRENT", "20"))
MAX_CAPITAL_PER_STRATEGY = float(os.getenv("MAX_CAPITAL_PER_STRATEGY", "0.05"))  # 5%

# Exit rules thresholds (can override defaults)
EXIT_RULE_TP_THRESHOLD = float(os.getenv("EXIT_RULE_TP_THRESHOLD", "0.25"))  # 25%
EXIT_RULE_MAX_LOSS = float(os.getenv("EXIT_RULE_MAX_LOSS", "1.0"))  # 100% of capital at risk

# Circuit breaker gates (same as Phase 1, but important for Phase 2)
CIRCUIT_BREAKER_ENABLED = True
MAX_DRAWDOWN = 0.12  # 12%
MAX_DAILY_LOSS = 0.05  # 5%
```

---

## Testing

### Unit Tests
```bash
pytest tests/test_phase2_full_bridge.py::TestStrategyRegistry -v
pytest tests/test_phase2_full_bridge.py::TestContractSelectorBridge -v
pytest tests/test_phase2_full_bridge.py::TestGreeksCalculator -v
pytest tests/test_phase2_full_bridge.py::TestExitRulesEngine -v
```

### Integration Test (Full Pipeline)
```bash
pytest tests/test_phase2_full_bridge.py::TestPhase2Pipeline -v
```

### End-to-End on Paper
```bash
# Run for 1-2 weeks on paper account, monitoring:
# 1. Orders fill correctly
# 2. Positions register in state.json
# 3. Entries appended to entries.jsonl
# 4. Greeks calculated accurately
# 5. Exit rules fire as expected
# 6. Nightly grader produces verdicts
```

---

## Monitoring Checklist

**During paper account validation:**

- [ ] Strategy scanner loads all 20 strategies
- [ ] Signals generated with confidence scores
- [ ] Contracts selected and match expected strikes/expiries
- [ ] Greeks calculated (delta, gamma, vega, theta)
- [ ] Circuit breaker gates work (no rogue trades)
- [ ] Multi-leg execution fills properly
- [ ] Dual-ledger write succeeds (state.json + entries.jsonl)
- [ ] Positions monitor for exits (13 rules firing)
- [ ] Nightly grader produces verdict
- [ ] Slack alerts post correctly
- [ ] P&L tracking matches manual verification

---

## Key Files & Line References

| Component | File | Key Lines |
|-----------|------|-----------|
| Strategy Registry | `src/strategies/shadow_bridge/strategy_registry.py` | 56-214 |
| Contract Selector | `src/strategies/shadow_bridge/contract_selector.py` | 9-201 |
| Greeks Calc | `src/strategies/shadow_bridge/greeks_calculator.py` | All |
| Exit Rules | `src/strategies/shadow_bridge/exit_rules_engine.py` | 19-167 |
| Market Adapter | `src/strategies/shadow_bridge/market_data_adapter.py` | All |
| **Phase 2 Coordinator** | `src/phase2_coordinator.py` | 25-286 |
| **Phase 1 Integration** | `src/phase2_coordinator.py` | **Line 215-223** (DualLedgerWriter call) |
| Tests | `tests/test_phase2_full_bridge.py` | All |

---

## Rollout Strategy

**Week 1-2: Paper Account Validation**
- `PHASE2_ENABLED=false` (scanner runs but doesn't execute)
- Monitor for 2 weeks
- Verify all 13 exit rules fire correctly
- Validate P&L tracking

**Week 3: Production - Start Small**
- `PHASE2_ENABLED=true` on live account
- `MAX_POSITIONS_CONCURRENT=5` (start with 5 strategies max)
- `MAX_CAPITAL_PER_STRATEGY=0.02` (start with 2% max)
- Monitor for 1 week

**Week 4+: Ramp to Full**
- `MAX_POSITIONS_CONCURRENT=20` (all 20 strategies)
- `MAX_CAPITAL_PER_STRATEGY=0.05` (5% per strategy)
- Standard risk gates apply (12% portfolio drawdown, 5% daily loss)

---

## Troubleshooting

### "No contracts found"
- Check Alpaca options chain is available for symbol
- Verify strike/expiry combination exists
- Check open interest is above minimum threshold (default: 100)

### "Circuit breaker rejected"
- Check portfolio drawdown (`(peak_val - current_val) / peak_val`)
- Check daily loss threshold
- Check position size vs 5% allocation
- Check correlation with SPY

### "Partial fills on multi-leg"
- One leg filled, others didn't
- Check liquidity on each leg
- Adjust spread width if needed
- Consider closing partial and re-entering later

### "Exit rule fired but position not closed"
- Check exit engine registered position
- Verify market hours (most exits require market orders)
- Check available buying power for forced close

### "Nightly grader shows UNPROVEN"
- Need minimum 25 trades for statistical significance
- Wealth score needs >= 20 for PROVEN verdict
- Run for longer period to accumulate trades

---

## What's Integrated with Phase 1?

✅ **DualLedgerWriter**: Every Phase 2 execution writes to both state.json and entries.jsonl  
✅ **Nightly Grader**: Grades Phase 2 trades the same as Phase 1 (e-process wealth)  
✅ **Circuit Breaker**: Same 4-gate protection (drawdown, position size, daily loss, correlation)  
✅ **Slack Alerts**: Phase 2 executions post same alerts as Phase 1  
✅ **Scorecard**: Phase 2 positions included in nightly scorecard.json verdict  

---

## Success Criteria

- [ ] All 20 Shadow strategies scan successfully
- [ ] Contract selector finds valid contracts for 95%+ of signals
- [ ] Greeks calculated within 0.5% of Black-Scholes
- [ ] Circuit breaker prevents rogue trades
- [ ] Multi-leg orders fill as expected (95%+ fill rate)
- [ ] Dual-ledger write succeeds for all trades
- [ ] All 13 exit rules fire when conditions met
- [ ] Nightly grader produces verdict
- [ ] 2 weeks of paper validation without errors
- [ ] Ready for production ramp

---

**Phase 2 Status**: ✅ **IMPLEMENTATION COMPLETE — READY FOR VALIDATION TESTING**

Next step: Deploy to paper account for 2-week validation (Task #22).

