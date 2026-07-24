# Full Audit Engine — Design Spec

Date: 2026-07-23
Status: Approved by user, pending implementation plan

## 1. Problem & Goal

The ticker search bar currently resolves a ticker and (as of the prior fix) runs a single
dual-agent LLM audit with no expiry awareness. The user wants a much richer, explicit
"Full Audit" action that, for one ticker:

- Shows price levels (support/resistance) first, above everything else.
- Scans strikes across multiple expiry horizons at once (this week's 0/2/3/5DTE-style
  dates, monthly, quarterly, LEAPS), picking strikes informed by those levels.
- Recommends concrete strategies (Cash-Secured Put, PMCC, LEAPS, spreads, etc.), ranked
  by probability of profit.
- Runs a 3-stage gate (Rules engine → LLM Agent → Circuit Breaker) that always executes
  all 3 stages and reports a synthesized pass/fail, automatically against the single
  top-ranked recommendation.
- Never runs any of this automatically on every keystroke/search — everything is behind
  one explicit "Full Audit" button, to control both compute cost and AI call budget.

## 2. Current State (verified in codebase)

- `DualAgentPipeline` (`src/options/agents.py`) — 2-stage Proposer/Validator LLM pipeline.
  No `expiry` parameter anywhere in its call chain; DTE is only ever a bucket label
  (`WEEKLY`/`MONTHLY`/`SEMI_ANNUAL`/`ANNUAL_LEAP`), never a real date.
- `RuleBasedAdapter` (`src/options/llm_adapters.py:110-238`) — 5 deterministic checks
  (liquidity/OI, spread, IV-rank warning, delta, position sizing). No DTE minimum rule.
- `audit_options_trade()` (`src/options/audit_engine.py:108-352`) — single-expiry engine.
  Already computes Greeks per strike via `get_contracts_for_expiry()`, already generates
  7 strategy alternatives (Short Put/CSP, Bull Put Spread, Long Call, PMCC, Bear Call
  Spread, Long Put, Iron Condor) ranked by a delta-derived PoP heuristic. This is the
  strongest existing building block — CSP and PMCC already exist here.
- `CircuitBreaker` (`src/risk/circuit_breaker.py`) — fully built (drawdown, position-size,
  daily-loss, correlation checks) but **never called from any options-audit endpoint** in
  `api.py` — only used in the live order-execution path (`coordinator.py`, `executor.py`).
- IV Rank — no real historical-IV-percentile source anywhere. Currently either a formula
  derived from an assumed volatility (`greeks.py`), or a hardcoded default (`35.0`/`50.0`).
  Decision: keep this as a labeled "IV Proxy," not a real percentile rank, for this spec.
- No support/resistance/pivot/volume-profile logic exists anywhere in the repo today.
- Local daily-bar cache exists at `data/<TICKER>/*.jsonl` — one file per trading day,
  OHLCV + VWAP, 270+ days of history already present for common tickers (AAPL/SPY/MSFT
  checked directly). This is sufficient for level detection with no new data vendor.
- `_get_alpaca_account_info()` (`src/api.py:39`) already returns real paper-account cash,
  equity, buying power, and open positions — usable directly as CircuitBreaker input
  without needing a live `trading_client` handed into the audit request path.
- Frontend chart is TradingView's **free embed widget** (`embed-widget-advanced-chart.js`
  in `WhitelightCortexIntegratedPanel.jsx:103`) — this tier does not expose an API to read
  back user-drawn lines. "Manual levels" must be a separate, purpose-built input, not a
  read of the chart's own drawing tool.

## 3. Architecture Decision

**New, self-contained module**, existing files untouched:

```
src/options/full_audit/
  __init__.py
  levels.py        # Section 4 — range/pivot + volume profile + manual levels
  recommender.py   # Section 5 — multi-expiry bucketing + level-aware strike selection
  strategies.py    # Section 5 — strategy library (wraps/extends audit_engine.py alternatives + new LEAPS strategy)
  rules_engine.py  # Section 6 — unified deterministic rules (merges RuleBasedAdapter + audit_options_trade rules + new min-DTE rule)
  gate.py          # Section 6 — 3-stage synthesis (Rules → Agent → CircuitBreaker, always-all-3)
```

This module *calls into* existing code (`greeks.py`, `audit_engine.py`'s
`get_contracts_for_expiry`, `agents.py`'s `DualAgentPipeline`, `llm_adapters.py`,
`circuit_breaker.py`) rather than modifying it. Every currently-working endpoint
(`/api/options/audit`, `/evaluate_dual_agent`, `/scan_watchlist`) stays exactly as-is.
This was chosen over (a) extending the existing files in place — higher regression risk
to already-working chain/conditional-order/watchlist UI — and (c) a full package
restructure — most disruptive, not justified for a first version of a large new feature.

## 4. Price Level Engine (`levels.py`)

**Inputs:** ticker, `volume_profile_window` (one of `1W`/`1M`/`3M`/`6M`/`1Y`, default `1M`).

**Sources, computed and merged into one output:**

1. **Rolling range + pivot points** — from local daily-bar cache (`data/<TICKER>/*.jsonl`),
   falling back to a live Alpaca daily-bars fetch (same pattern as
   `CircuitBreaker.fetch_30day_bars_from_alpaca`) if no local cache exists. Computed at
   3 lookbacks (5-day/20-day/60-day): rolling high/low range, and classic floor-trader
   pivot points (PP, R1/R2, S1/S2) off the prior period's high/low/close.
2. **Volume profile** — Alpaca historical **minute** bars (`StockBarsRequest` with
   `TimeFrame.Minute`, same client already used for daily bars, no new vendor) over the
   selected window. Volume bucketed by price to find Point of Control (POC) and Value
   Area High/Low (band holding ~70% of volume).
3. **Manual levels** — user-entered price + label, saved per ticker in a new small JSON
   store (`data/levels/<TICKER>.json`), independent of the TradingView widget entirely.
   Simple CRUD: add/list/delete.

**Output format** (matches the reference UI the user provided): all levels from all 3
sources are merged into one sorted list below current price and one above, deduplicated
and capped at 5 each:

```json
{
  "ticker": "TSLA",
  "current_price": 316.11,
  "levels_below": [276.62, 281.42, 290.44, 300.79, 309.93],
  "levels_above": [336.30, 352.17, 358.39, 369.03, 383.46]
}
```

This is always the first thing shown when Full Audit runs.

## 5. Multi-Expiry Recommendation Engine (`recommender.py`, `strategies.py`)

**Expiry bucketing** — pull the ticker's real available expirations (reusing the same
Alpaca `GetOptionContractsRequest`-based approach already proven in
`audit_engine.py::get_contracts_for_expiry`, for consistency with the working path)
and bucket by real DTE rather than assuming every ticker has the same expiry cadence:

| Bucket | DTE range | Notes |
|---|---|---|
| This Week | ≤ 7 calendar days | For SPY/QQQ (daily expiries) this naturally yields 0/2/3/5DTE; for tickers with only Friday weeklies, this bucket has just the one date. |
| Monthly | ~30–45 DTE | Nearest standard monthly cycle. |
| Quarterly | ~75–105 DTE | Nearest ~3-month-out expiry. |
| LEAPS | ≥ 270 DTE | Longest available if nothing is ≥270. |

**Strike selection per expiry** — for each expiry in each bucket, fetch contracts via the
existing `get_contracts_for_expiry()` (already expiry-aware, already computes Greeks),
then pick candidates using the Level Engine's output: calls target the nearest OTM strike
plus strikes at/near each resistance level; puts mirror that off support levels. Rank
candidates by IV proxy (sell premium when high, buy when low — existing logic), delta
banding appropriate to the DTE, and liquidity (OI/spread — existing `RuleBasedAdapter`
criteria).

**Strategy library** — Cash-Secured Put and PMCC already exist in `audit_engine.py`'s
alternative-generation logic and are reused as-is per expiry bucket. The one new addition:
an outright **LEAPS** strategy (buy deep-ITM/near-ATM long-dated call, ~0.70–0.80 delta,
stock-replacement position) distinct from PMCC's paired long/short-leg structure, gated
to the LEAPS bucket.

**Cost profile:** pure math, no LLM calls — safe to run on every explicit Full Audit click
without touching AI budget.

**Cross-bucket "top pick" selection** — each bucket ranks its own cards by PoP
internally; the single card that Section 6's gate auto-runs against is whichever card
has the single highest PoP across *all* buckets combined (a flat sort of every card from
every bucket, descending by `probability_of_profit`, take the first). Ties broken by
preferring the shorter DTE (nearer-term, matches the "weekly-first" spirit of the user's
original example).

## 6. 3-Stage Synthesis Gate (`rules_engine.py`, `gate.py`)

Runs sequentially, single-threaded (explicitly acceptable — this only fires once per
explicit Full Audit click, latency is not a concern). **All 3 stages always run to
completion**, no short-circuiting on early failure, so the user sees all three verdicts
every time:

1. **Rules Engine** — unified module merging `RuleBasedAdapter`'s liquidity/spread/delta/
   position-sizing checks with `audit_options_trade`'s IV/DTE/bias logic, plus a new
   minimum-DTE gate. PASS/FAIL + reasons.
2. **Agent Audit** — existing `DualAgentPipeline`, now given the specific expiry date +
   selected contract + level context (e.g. "price testing resistance at $700") so its
   reasoning is level-aware instead of generic. PASS/FAIL (`execution_ready`) + reasoning.
3. **Circuit Breaker** — existing `CircuitBreaker.can_execute()`, fed real paper-account
   state from `_get_alpaca_account_info()` (cash/equity/positions) — no live
   `trading_client` needed in the request path. PASS/FAIL + reason.

**Synthesis response:**

```json
{
  "overall": "AUDIT PASSED",
  "stages": {
    "rules":   { "pass": true, "reason": "Strike within acceptable range" },
    "agent":   { "pass": true, "reasoning": "Delta within bounds, liquidity adequate" },
    "circuit": { "pass": true, "reason": "Account drawdown OK" }
  },
  "recommendation": "BUY CALL 700C 10DTE"
}
```

`overall` is `"AUDIT FAILED"` if any stage fails; each stage's own pass/fail and reason
are always present since all 3 always run.

## 7. API Endpoints

- `POST /api/options/full_audit` — the one button's action. Runs Levels → multi-expiry
  Recommendation → auto-runs the 3-stage Gate against the single top-ranked
  strategy/strike/expiry across all buckets. Returns levels + full recommendation grid +
  gate synthesis in one response.
- `POST /api/options/full_audit/gate` — re-run the 3-stage gate against a different,
  user-picked card from the grid (secondary action, not the primary button).
- `GET /api/options/levels/manual?ticker=` / `POST` / `DELETE` — CRUD for user-entered
  manual levels.

## 8. Frontend Flow

1. Search bar unchanged: Go resolves the ticker and shows the chart, as today.
2. A new explicit **"Full Audit"** button appears once a ticker is active (not auto-run on
   search, to control compute cost and AI budget as requested).
3. Clicking it calls `POST /api/options/full_audit` and renders, in order:
   - Levels card first (ticker, current price, Levels Below / Levels Above — merged,
     capped 5 each, matching the reference format provided).
   - Multi-expiry recommendation grid (4 bucket tabs, ranked strategy cards).
   - The 3-stage gate verdict for the auto-selected top pick, using the same inline
     dropdown-panel pattern already shipped for the search-bar audit.
4. Clicking any other card re-runs just the gate (`/full_audit/gate`) against that
   alternative, updating the verdict panel without re-fetching levels/grid.

## 9. Error Handling

- No local/Alpaca daily bars available for a ticker → Levels engine returns empty
  below/above arrays with a clear "insufficient history" note, rest of the pipeline
  still runs (recommendation grid can still work off current price alone).
- No expirations available in a bucket (e.g. no LEAPS listed for a small-cap) → that
  bucket tab shows "No contracts available for this horizon" instead of erroring.
- Any of the 3 gate stages throwing an exception → treated as a FAIL for that stage with
  the exception message as the reason, not a hard 500 — matches existing
  `auditNewWatchlistTicker` exception-handling pattern on the frontend.

## 10. Testing

- Unit tests for `levels.py` against fixture daily-bar data (known range/pivot/POC output
  for a synthetic price series).
- Unit tests for expiry bucketing against a fixed list of mock expiration dates (verifies
  correct bucket assignment at boundary DTEs).
- Unit tests for the unified rules engine (each existing rule + new min-DTE rule,
  pass and fail cases).
- Unit test for gate synthesis: all-pass, each single-stage-fail, multi-stage-fail cases,
  confirming all 3 stages always populate in the response regardless of failures.
- Manual browser verification (as done for the prior search-bar fix) of the full click
  flow: Go → Full Audit → levels shown first → grid → gate verdict → click alternate
  card → gate re-runs.
