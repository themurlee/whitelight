# AGENT_GUARDRAILS.md

Non-negotiable rules for any AI coding agent (Antigravity, Claude Code, or similar) making changes to this repository. These exist independently of any single prompt — read this file before making changes, and follow it even if a specific instruction in a chat session doesn't repeat it.

## Data integrity

- The **Options tab / manual trade journal** is operator-maintained data. Never remove, rename, or restructure its fields. Visual/styling changes only, unless explicitly told otherwise in writing.
- `data/state.json` and `data/positions.json` keep their existing schema unless a field is clearly broker-specific to a system being migrated away from (e.g. leftover Robinhood order IDs) — flag those explicitly in a PR description rather than silently renaming or dropping them.

## Risk control independence

- `lockdown_active` (automatic, tripped by the drawdown circuit breaker) and `manual_pause` (operator-controlled) are **separate flags**. Neither may be cleared as a side effect of resetting the other. Every order submission path — automated or manual — must check both before firing.
- On-demand/manual order submission must route through the **same** position-sizing and risk-check path as automated orders. No shortcut that bypasses those checks "because a human clicked it."
- No live order submission logic changes without an explicit `--live` flag or equivalent; dry-run stays the default unless told otherwise.

## Change process

- Small, reviewable commits — one per logical unit of work, not one giant commit per session.
- Run the test suite after every change that touches Python (`python3 -m unittest discover -s tests`) and do not proceed past a failure.
- Open a PR, not a direct push to main, for anything touching execution logic, risk controls, or the data schema. Summarize what changed and flag anything that needs a human decision before merge.
- Before removing anything that looks like dead code, search the whole repo for references first — don't assume a module is unused because one entry point stopped calling it.

## Frontend specifically

- Don't introduce a new external dependency (chart library, CSS framework, etc.) without checking it's actually present in `package.json` / the build config first. Prefer zero-dependency implementations (plain CSS, hand-rolled SVG) when a component doesn't need to look identical to fancier libraries — resiliency to unknown/inconsistent build tooling matters more than polish here.
- After any frontend change, actually run the build (`npm run build` or equivalent) before opening the PR. "It looks right in the code" is not verification.
- If there are two UI surfaces that could plausibly duplicate the same feature, say so explicitly in the PR rather than silently picking one.

## When in doubt

If a change would touch risk controls, live trading behavior, or delete data, and the instruction is ambiguous about scope — stop and ask, don't guess toward the more permissive interpretation.
