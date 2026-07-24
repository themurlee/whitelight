from typing import Dict, Optional


def evaluate_rules(
    selected_contract: Dict,
    iv_rank: float,
    dte: int,
    account_equity: Optional[float] = None,
    order_value: Optional[float] = None,
) -> Dict:
    """Unified deterministic rules gate: liquidity, spread, delta, min-DTE, position sizing.

    Merges RuleBasedAdapter's checks (liquidity/spread/delta/sizing) with a new
    minimum-DTE gate. Does not touch RuleBasedAdapter or audit_engine.py.
    """
    checks = []

    bid = float(selected_contract.get("bid", 0))
    ask = float(selected_contract.get("ask", 0))
    midpoint = float(selected_contract.get("midpoint", (bid + ask) / 2.0 if (bid or ask) else 0))
    open_interest = int(selected_contract.get("open_interest", 0))
    delta = abs(float(selected_contract.get("greeks", {}).get("delta", 0.5)))

    # 1. Liquidity
    liquidity_pass = open_interest >= 500
    checks.append({
        "name": "Liquidity", "pass": liquidity_pass,
        "detail": f"Open Interest {open_interest} ({'>=' if liquidity_pass else '<'} 500 required)",
    })

    # 2. Spread
    spread_pct = ((ask - bid) / midpoint * 100.0) if midpoint > 0 else 0.0
    spread_pass = spread_pct <= 10.0
    checks.append({
        "name": "Spread", "pass": spread_pass,
        "detail": f"Bid-Ask spread {spread_pct:.1f}% ({'<=' if spread_pass else '>'} 10% limit)",
    })

    # 3. Minimum DTE (new — did not exist in RuleBasedAdapter or audit_engine.py)
    min_dte_pass = dte >= 1
    checks.append({
        "name": "Minimum DTE", "pass": min_dte_pass,
        "detail": f"DTE is {dte} ({'>=' if min_dte_pass else '<'} 1 day required)",
    })

    # 4. Delta
    delta_pass = delta >= 0.35
    checks.append({
        "name": "Delta", "pass": delta_pass,
        "detail": f"Delta {delta:.2f} ({'>=' if delta_pass else '<'} 0.35 required)",
    })

    # 5. Position sizing (only checked if account context provided)
    if account_equity is not None and order_value is not None and account_equity > 0:
        max_alloc = account_equity * 0.02
        sizing_pass = order_value <= max_alloc
        checks.append({
            "name": "Position Sizing", "pass": sizing_pass,
            "detail": f"Order value ${order_value:.2f} vs max allocation ${max_alloc:.2f} (2% of equity)",
        })
    else:
        checks.append({"name": "Position Sizing", "pass": True, "detail": "No account context provided; skipped"})

    overall_pass = all(c["pass"] for c in checks)
    reason = "All rules passed" if overall_pass else next(c["detail"] for c in checks if not c["pass"])

    return {"pass": overall_pass, "checks": checks, "reason": reason}
