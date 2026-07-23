# Phase 2 Validation: Paper Account Testing Runbook

**Timeline**: 2 weeks (2026-07-23 to 2026-08-06)  
**Environment**: Alpaca paper trading account  
**Success Criteria**: All components operational, no missed exits, P&L tracking accurate  
**Owner**: You  
**Frequency**: Daily morning checks, nightly grader review

---

## Pre-Launch Checklist (Today)

### ✅ Environment Setup
- [ ] Alpaca paper account active and funded ($100k+ recommended)
- [ ] API_KEY and SECRET_KEY set in environment
- [ ] Shadow repo path configured (`SHADOW_REPO_PATH` env var)
- [ ] Slack webhook URL configured for alerts
- [ ] Data directory exists (`data/` folder for state.json, entries.jsonl, etc.)

### ✅ Code Verification
- [ ] Phase 2 coordinator imports without errors: `python3 -c "from src.phase2_coordinator import run_phase2_pipeline"`
- [ ] Phase 1 grader imports without errors: `python3 -c "from src.integration.nightly_grader_task import run_nightly_grading"`
- [ ] All 20 strategies load: `python3 << 'EOF'` 
  ```python
  from src.strategies.shadow_bridge.strategy_registry import StrategyRegistry
  import src.config as config
  registry = StrategyRegistry(config.SHADOW_REPO_PATH)
  strategies = registry.load_all_strategies()
  print(f"Loaded {len(strategies)} strategies")
  ```

### ✅ Configuration Review
- [ ] `PHASE2_ENABLED=false` (start with scanning only, no execution)
- [ ] `MAX_POSITIONS_CONCURRENT=5` (conservative start)
- [ ] `MAX_CAPITAL_PER_STRATEGY=0.02` (2% max per strategy)
- [ ] Circuit breaker enabled with defaults

---

## Week 1: Dry-Run + Monitoring (No Live Orders)

### Day 1-2: Scanner Validation
**Goal**: Verify all 20 strategies scan without errors

```bash
# Run scanner in dry-run mode (no orders)
python3 -m src.phase2_coordinator SPY QQQ AAPL --dry-run

# Expected output:
# - [PHASE2_COORDINATOR] [INFO] Loaded 20 strategies from Shadow repository
# - [PHASE2_COORDINATOR] [INFO] Scan complete. Found N strategy scan signals
# - [PHASE2_COORDINATOR] [INFO] Identified X entry signals to evaluate
# - For each signal: [DRY RUN] Would execute...
# - ✅ [whitelight-phase2] Cycle complete
```

**Daily checks:**
- [ ] Day 1: 3x daily (9am, 12pm, 3pm ET) - Check scanner output
- [ ] Day 2: 2x daily (9am, 4pm ET) - Verify consistency

**What to monitor:**
- Scanner runs to completion without crashes
- Strategies scan consistently (same or similar signals daily)
- Contract selection succeeds for 90%+ of signals
- No timeout errors

---

### Day 3-5: Greeks Calculation Validation
**Goal**: Verify Greeks calculations and position tracking

**Action**: Keep dry-run mode, but track simulated positions

```bash
# Continue dry-run
python3 -m src.phase2_coordinator SPY QQQ AAPL --dry-run

# Manually verify Greeks outputs
grep "greeks" data/entries.jsonl | head -5 | jq '.greeks'

# Expected: delta, gamma, vega, theta for each combo
```

**Daily checks:**
- [ ] Day 3-5: 1x daily (9am ET) - Run scanner
- [ ] Check greeks output is populated
- [ ] Verify Greeks are within reasonable ranges (delta 0-1, etc)

**What to monitor:**
- Greeks calculations don't crash
- Delta, gamma, vega, theta are numeric and bounded
- Greeks make sense for selected contracts (ATM delta ~0.5)

---

### Day 6-7: Circuit Breaker Validation
**Goal**: Verify circuit breaker gates work correctly

```bash
# Still in dry-run mode
python3 -m src.phase2_coordinator SPY QQQ AAPL --dry-run

# Check circuit breaker logs
grep -i "circuit\|breaker\|refused" data/journal/trade_log.md | tail -20
```

**Daily checks:**
- [ ] Day 6-7: 1x daily - Run scanner, check breaker logs
- [ ] Verify no signals are incorrectly rejected

**What to monitor:**
- Circuit breaker allows reasonable signals through
- Circuit breaker doesn't false-alarm on low-risk trades
- Rejection reasons are clear (drawdown, position size, etc)

---

## Week 2: Live Trading + Daily Monitoring

### Day 8: Go Live (Conservative)
**Goal**: Execute first few trades on paper account

**Before executing:**
- [ ] Review last 7 days of dry-run output
- [ ] Confirm you understand exit rules (all 13)
- [ ] Alpaca paper account has $100k+ buying power
- [ ] Slack notifications enabled

**Action**: Enable live execution
```bash
# Update config
export PHASE2_ENABLED="true"
export MAX_POSITIONS_CONCURRENT=3  # Start with just 3 strategies
export MAX_CAPITAL_PER_STRATEGY=0.02  # 2% per strategy

# Run first live scan
python3 -m src.phase2_coordinator SPY --dry-run=false

# Expected:
# - ✅ [whitelight-phase2] Executed strategy_001 on SPY
# - Position registered with exit rules engine
# - Slack alert: "✅ [whitelight-phase2] Executed..."
# - state.json updated with active_positions
# - entries.jsonl appended with execution record
```

**Immediate checks (within 5 minutes):**
- [ ] Alpaca paper account shows filled orders
- [ ] state.json `active_positions` array has new position
- [ ] entries.jsonl has new execution entry
- [ ] Slack alert posted successfully

---

### Day 9-14: Daily Monitoring
**Morning routine (9am ET, 15 min):**
```bash
# 1. Check if any exit rules fired overnight
grep "fired\|exit" data/journal/trade_log.md | tail -10

# 2. Verify Alpaca paper account positions
# (Log into Alpaca UI and check open positions)

# 3. Check state.json for active positions
jq '.active_positions | length' data/state.json
# Should be <= MAX_POSITIONS_CONCURRENT

# 4. Verify entries.jsonl has recent entries
tail -5 data/entries.jsonl | jq '.'
```

**Intraday monitoring (at least 1x):**
- [ ] Check Alpaca paper account in UI
- [ ] Verify no unexpected positions closed
- [ ] Monitor P&L (should be small, ±5% typical on paper)
- [ ] Note any exit rules that fired

**Evening routine (4:30pm ET, 10 min):**
```bash
# Run nightly grader (Phase 1 integration)
python3 -m src.integration.nightly_grader_task

# Expected output:
# - Loads entries.jsonl (includes Phase 2 trades)
# - Computes e-process wealth
# - Saves scorecard.json
# - Posts Slack: "✅ [whitelight-grader] UNPROVEN (wealth=X, n=Y)"
```

**End of day checklist (5pm ET):**
- [ ] Nightly grader completed without errors
- [ ] Scorecard saved to data/scorecard.json
- [ ] Slack alert posted with verdict
- [ ] No unexpected closes
- [ ] No error logs in trade_log.md

---

## Daily Monitoring Template

**Copy this and run daily (2 weeks = 10 business days):**

```markdown
## Day X (YYYY-MM-DD) - Phase 2 Validation

### Morning (9:00 AM ET)
- [ ] Scanner ran successfully
- [ ] Signals generated: _____ entry signals
- [ ] Contracts selected: _____ successful
- [ ] Strategies active: _____
- [ ] Issues: _____

### Portfolio Status
- [ ] Active positions in Alpaca: _____
- [ ] Active positions in state.json: _____
- [ ] Match? YES / NO
- [ ] Total capital at risk: $_____
- [ ] Daily P&L: $_____

### Exit Rules
- [ ] Rules checked: _____
- [ ] Rules fired: _____
- [ ] Exits executed: _____
- [ ] Any unexpected exits? YES / NO

### Nightly Grader (4:30 PM ET)
- [ ] Grader ran: YES / NO
- [ ] Verdict: PROVEN / UNPROVEN / LOSER
- [ ] Wealth score: _____
- [ ] Trade count: _____
- [ ] Win rate: _____%

### Issues & Notes
- [ ] Bugs discovered: _____
- [ ] Performance notes: _____
- [ ] Recommendations for adjustment: _____
```

---

## Exit Rules Validation Checklist

Over the 2-week period, verify all 13 exit rules work:

| Rule | Target | Day Verified | Status |
|------|--------|---------|--------|
| 1. Profit Target (25%) | See at least 1 position hit +25% | _____ | ✅ / ⏳ |
| 2. Theta Decay (50%) | See at least 1 position exit on theta | _____ | ✅ / ⏳ |
| 3. Earnings Blackout | See at least 1 earnings exit | _____ | ✅ / ⏳ |
| 4. Macro Print | See blackout on CPI/jobs print | _____ | ✅ / ⏳ |
| 5. Vega Collapse (IV drop > 20) | See at least 1 IV collapse exit | _____ | ✅ / ⏳ |
| 6. Gamma Risk | See at least 1 gamma exit | _____ | ✅ / ⏳ |
| 7. Technical Breakdown | See at least 1 technical exit | _____ | ✅ / ⏳ |
| 8. DTE (≤14 days) | See at least 1 DTE exit | _____ | ✅ / ⏳ |
| 9. Calendar Vega | See at least 1 calendar vega exit | _____ | ✅ / ⏳ |
| 10. Correlation (≥0.8) | See at least 1 correlation exit | _____ | ✅ / ⏳ |
| 11. Margin Pressure (Reg-T < 20%) | Unlikely on paper, but check logs | _____ | ✅ / ⏳ |
| 12. Voluntary Exit | Manual close test (close 1 position manually) | _____ | ✅ / ⏳ |
| 13. Max Loss Circuit | Set 1 stop-loss intentionally | _____ | ✅ / ⏳ |

---

## Red Flags (STOP & INVESTIGATE)

If you see ANY of these, pause and investigate before continuing:

🚨 **CRITICAL STOPS**
- [ ] Crash or exception in phase2_coordinator.py
- [ ] Crash or exception in nightly_grader_task.py
- [ ] Orders filled but not recorded in state.json
- [ ] Positions closed but no exit rule fired (orphaned exit)
- [ ] Nightly grader verdict doesn't match manual P&L
- [ ] Slack alerts not posting

🔴 **INVESTIGATION REQUIRED**
- [ ] Contract selection fails for > 10% of signals
- [ ] Greeks calculations missing or NaN
- [ ] Circuit breaker rejecting > 50% of signals
- [ ] Exit rules not firing when they should
- [ ] Partial fills on multi-leg orders
- [ ] P&L tracking off by > 5%

⚠️ **YELLOW FLAGS (Monitor)**
- [ ] Only 1-2 strategies generating signals (expect 5-10)
- [ ] Low win rate (< 40% is concerning)
- [ ] High correlation exits firing frequently
- [ ] Nightly grader showing LOSER verdict

---

## Troubleshooting Commands

### If scanner crashes
```bash
# Check logs
tail -50 data/journal/trade_log.md

# Verify strategies load
python3 -c "from src.strategies.shadow_bridge.strategy_registry import StrategyRegistry; import src.config as config; print(len(StrategyRegistry(config.SHADOW_REPO_PATH).load_all_strategies()))"
```

### If positions don't show in state.json
```bash
# Check state.json exists and is valid
cat data/state.json | jq '.active_positions | length'

# Check entries.jsonl has the trade
tail -1 data/entries.jsonl | jq '.'
```

### If nightly grader fails
```bash
# Check entries.jsonl has Phase 2 trades
grep "whitelight" data/entries.jsonl | wc -l

# Run grader manually with verbose output
python3 -c "from src.integration.nightly_grader_task import run_nightly_grading; run_nightly_grading()"
```

### If exits don't fire
```bash
# Check exit rules engine logs
grep -i "exit\|rule" data/journal/trade_log.md | tail -20

# Manually check position state
jq '.active_positions[0]' data/state.json
```

---

## End of Validation: Go/No-Go Decision

**On 2026-08-06**, evaluate against these criteria:

| Criterion | Target | Actual | Pass? |
|-----------|--------|--------|-------|
| Scanner uptime | 100% | ___% | ✅ / ❌ |
| Contract selection success | 90%+ | __% | ✅ / ❌ |
| Greeks accuracy | ±0.5% BS | ±_% | ✅ / ❌ |
| Circuit breaker works | 0 rogue trades | __ | ✅ / ❌ |
| All 13 exit rules fire | 80%+ tested | _/13 | ✅ / ❌ |
| Nightly grader works | Produces verdict | ✅ / ❌ | ✅ / ❌ |
| P&L tracking accuracy | ±2% | ±_% | ✅ / ❌ |
| Zero orphaned positions | 100% tracked | __% | ✅ / ❌ |
| Slack alerts post | 100% | __% | ✅ / ❌ |

**Decision**:
- **GO**: All criteria met → Proceed to production ramp (Task #23)
- **NO-GO**: Bugs found → Fix and re-validate (1-2 weeks)

---

## Production Ramp (If GO Decision)

Once paper account validation succeeds:

**Week 1 of Production:**
- `MAX_POSITIONS_CONCURRENT=5` (5 strategies)
- `MAX_CAPITAL_PER_STRATEGY=0.02` (2% per strategy)
- Monitor daily for first week

**Week 2-4 of Production:**
- Gradually increase to `MAX_POSITIONS_CONCURRENT=10`
- Gradually increase to `MAX_CAPITAL_PER_STRATEGY=0.03` (3% per strategy)
- Continue daily monitoring

**Week 4+: Full Production:**
- `MAX_POSITIONS_CONCURRENT=20` (all strategies)
- `MAX_CAPITAL_PER_STRATEGY=0.05` (5% per strategy)
- Maintain daily monitoring + weekly reviews

---

**Validation Timeline**: 2 weeks (10 business days)  
**Start Date**: 2026-07-23  
**Target Go-Live**: 2026-08-06  
**Owner**: You  

**Status**: READY TO BEGIN ✅

