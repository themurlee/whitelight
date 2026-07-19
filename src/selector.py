"""
WhiteLight Systematic Trading & Analysis Pipeline - Options Chain Selector
Filters available options contracts from the Alpaca options chain data structures
based on target Days to Expiration (DTE) and target Delta parameters.
Also provides multi-leg defined-risk structures: vertical credit spreads and iron condors.
"""

from typing import List, Dict, Optional
from datetime import datetime


def calculate_dte(expiration_date_str: str, current_date_str: str) -> int:
    """
    Calculate the Days To Expiration (DTE) between an option expiration date
    and the evaluation current date.
    Expects format YYYY-MM-DD for both parameters.
    """
    try:
        exp_date = datetime.strptime(expiration_date_str, "%Y-%m-%d")
        curr_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        return (exp_date - curr_date).days
    except ValueError as e:
        raise ValueError(
            f"Invalid date format. Expected YYYY-MM-DD. Error: {e}"
        )


def filter_options_chain(
    contracts: List[Dict],
    option_type: str,
    current_date_str: str,
    target_dte: int = 30,
    target_delta: float = 0.40
) -> Optional[Dict]:
    """
    Filters the options chain to find the optimal contract matching:
    1. The expiration date closest to target_dte days from current_date_str.
    2. The contract on that expiration date with option_type ("call" or "put")
       having delta closest to target_delta (0.40 for calls, -0.40 for puts).

    Parameters:
    - contracts: List of dicts representing contracts.
      Each contract must have:
      - 'expiration_date' (str, YYYY-MM-DD)
      - 'option_type' (str, 'call' or 'put')
      - 'delta' (float, greek value; typically negative for puts)
      - 'strike_price' (float)
      - 'symbol' (str)
    - option_type: 'call' or 'put'
    - current_date_str: Current date as string (YYYY-MM-DD)
    - target_dte: Target days to expiration (default 30)
    - target_delta: Target delta (default 0.40; handled as absolute value)

    Returns:
    - The selected contract dict, or None if no matching contract is found.
    """
    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")

    # Filter by option type and extract expiration dates
    typed_contracts = [
        c for c in contracts
        if c.get("option_type", "").lower() == option_type
    ]
    if not typed_contracts:
        return None

    # Step 1: Find expiration date closest to target DTE
    expirations = list(set(c["expiration_date"] for c in typed_contracts if "expiration_date" in c))
    if not expirations:
        return None

    best_exp_date = None
    min_dte_diff = float("inf")

    for exp in expirations:
        try:
            dte = calculate_dte(exp, current_date_str)
            # Only consider expirations in the future (or today)
            if dte >= 0:
                diff = abs(dte - target_dte)
                if diff < min_dte_diff:
                    min_dte_diff = diff
                    best_exp_date = exp
        except ValueError:
            continue

    if best_exp_date is None:
        return None

    # Step 2: Filter contracts of the chosen expiration date
    candidate_contracts = [
        c for c in typed_contracts
        if c.get("expiration_date") == best_exp_date
    ]

    # Step 3: Find contract with delta closest to target delta
    # Calls have positive delta, Puts have negative delta
    adjusted_target_delta = target_delta if option_type == "call" else -target_delta

    best_contract = None
    min_delta_diff = float("inf")

    for contract in candidate_contracts:
        delta = contract.get("delta")
        if delta is None:
            continue

        try:
            delta_val = float(delta)
            diff = abs(delta_val - adjusted_target_delta)
            if diff < min_delta_diff:
                min_delta_diff = diff
                best_contract = contract
            # Tie breaker: prefer higher volume or open interest if present
            elif diff == min_delta_diff and best_contract is not None:
                curr_vol = float(contract.get("volume", 0))
                best_vol = float(best_contract.get("volume", 0))
                if curr_vol > best_vol:
                    best_contract = contract
        except ValueError:
            continue

    return best_contract


# --------------------------------------------------------------------------- #
# Defined-risk multi-leg structures
# --------------------------------------------------------------------------- #

def _check_liquidity(
    contracts: List[Dict],
    max_spread_pct: float = 0.10
) -> List[Dict]:
    """
    Filter out illiquid contracts where (ask - bid) / mid > max_spread_pct.
    Contracts without bid/ask data pass through (caller's risk).
    """
    liquid = []
    for c in contracts:
        bid = c.get("bid")
        ask = c.get("ask")
        if bid is None or ask is None:
            liquid.append(c)  # no spread data -> pass through
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0:
            liquid.append(c)
            continue
        spread_pct = (ask - bid) / mid
        if spread_pct <= max_spread_pct:
            liquid.append(c)
    return liquid


def _find_by_delta(
    contracts: List[Dict],
    option_type: str,
    target_delta: float
) -> Optional[Dict]:
    """Return contract in `contracts` with delta closest to target_delta (absolute)."""
    signed_target = target_delta if option_type == "call" else -target_delta
    best = None
    best_diff = float("inf")
    for c in contracts:
        if c.get("option_type", "").lower() != option_type:
            continue
        delta = c.get("delta")
        if delta is None:
            continue
        diff = abs(float(delta) - signed_target)
        if diff < best_diff:
            best_diff = diff
            best = c
    return best


def _find_by_strike(
    contracts: List[Dict],
    option_type: str,
    target_strike: float
) -> Optional[Dict]:
    """Return contract of given option_type with strike closest to target_strike."""
    best = None
    best_diff = float("inf")
    for c in contracts:
        if c.get("option_type", "").lower() != option_type:
            continue
        strike = c.get("strike_price")
        if strike is None:
            continue
        diff = abs(float(strike) - target_strike)
        if diff < best_diff:
            best_diff = diff
            best = c
    return best


def vertical_credit_spread(
    underlying: str,
    contracts: List[Dict],
    direction: str,
    current_date_str: str,
    target_delta: float = 0.20,
    width: float = 5.0,
    target_dte: int = 30,
    max_spread_pct: float = 0.10,
) -> Optional[Dict]:
    """
    Build a vertical credit spread (bull put or bear call) and return risk metrics.

    direction : "bull_put"  -> sell put at target_delta, buy put width points lower
                "bear_call" -> sell call at target_delta, buy call width points higher
    width     : distance in dollars between the two strikes
    max_spread_pct : maximum (ask-bid)/mid for each leg; illiquid chains rejected

    Returns dict with:
      short_leg, long_leg  : the two contract dicts selected
      net_credit           : credit received (short_leg mid - long_leg mid)
      max_loss             : width - net_credit (per share; multiply by 100 for 1 contract)
      max_profit           : net_credit
      breakeven            : single breakeven price
      net_delta            : short_leg delta + long_leg delta
      underlying           : ticker
    Or None if a suitable structure can't be built from the provided chain.
    """
    direction = direction.lower()
    if direction not in ("bull_put", "bear_call"):
        raise ValueError("direction must be 'bull_put' or 'bear_call'")

    option_type = "put" if direction == "bull_put" else "call"

    # Narrow to the expiration closest to target_dte
    expirations = sorted(set(c.get("expiration_date", "") for c in contracts if c.get("expiration_date")))
    best_exp = None
    min_diff = float("inf")
    for exp in expirations:
        try:
            dte = calculate_dte(exp, current_date_str)
            if dte >= 0 and abs(dte - target_dte) < min_diff:
                min_diff = abs(dte - target_dte)
                best_exp = exp
        except ValueError:
            continue
    if not best_exp:
        return None

    exp_contracts = [c for c in contracts if c.get("expiration_date") == best_exp]
    liquid = _check_liquidity(exp_contracts, max_spread_pct)
    if not liquid:
        return None

    # Short leg: closest delta to target_delta
    short_leg = _find_by_delta(liquid, option_type, target_delta)
    if not short_leg:
        return None

    short_strike = float(short_leg["strike_price"])

    # Long leg: width points away (protective leg)
    if direction == "bull_put":
        long_strike_target = short_strike - width
    else:  # bear_call
        long_strike_target = short_strike + width

    long_leg = _find_by_strike(liquid, option_type, long_strike_target)
    if not long_leg:
        return None

    # Prices (use mid)
    def _mid(c: Dict) -> float:
        b = c.get("bid", 0) or 0
        a = c.get("ask", 0) or 0
        return (b + a) / 2.0

    short_mid = _mid(short_leg)
    long_mid = _mid(long_leg)
    net_credit = short_mid - long_mid

    actual_width = abs(float(long_leg["strike_price"]) - short_strike)
    max_loss = actual_width - net_credit
    max_profit = net_credit

    if direction == "bull_put":
        breakeven = short_strike - net_credit
    else:
        breakeven = short_strike + net_credit

    short_delta = float(short_leg.get("delta") or 0)
    long_delta = float(long_leg.get("delta") or 0)
    net_delta = short_delta + long_delta

    return {
        "structure": f"{underlying}_{direction}",
        "underlying": underlying,
        "expiration_date": best_exp,
        "direction": direction,
        "short_leg": short_leg,
        "long_leg": long_leg,
        "net_credit": round(net_credit, 4),
        "max_loss": round(max_loss, 4),
        "max_profit": round(max_profit, 4),
        "breakeven": round(breakeven, 4),
        "net_delta": round(net_delta, 4),
        "width": actual_width,
    }


def iron_condor(
    underlying: str,
    contracts: List[Dict],
    current_date_str: str,
    target_delta: float = 0.15,
    width: float = 5.0,
    min_iv_rank: float = 45.0,
    iv_rank: Optional[float] = None,
    target_dte: int = 30,
    max_spread_pct: float = 0.10,
) -> Optional[Dict]:
    """
    Build a 4-leg iron condor: bull put spread (lower) + bear call spread (upper).

    target_delta : delta for short put and short call legs
    width        : distance in dollars between each spread's strikes
    min_iv_rank  : minimum IV rank required to open (rejects low-vol environments).
                   Pass iv_rank as the current measured IV rank (0-100).
                   Pass iv_rank=None to skip the IV filter (e.g. in backtests).
    max_spread_pct: liquidity filter per leg

    Returns dict with:
      bull_put_spread, bear_call_spread : each a dict from vertical_credit_spread()
      net_credit         : combined credit from both spreads
      max_loss           : width - net_credit (for one spread width; both widths assumed equal)
      max_profit         : net_credit
      breakevens         : [lower_breakeven, upper_breakeven]
      net_delta          : combined delta
      iv_rank_filter_met : bool (True if iv_rank >= min_iv_rank or iv_rank is None)
    Or None if a valid structure can't be built.
    """
    # IV rank filter
    iv_filter_met = (iv_rank is None) or (iv_rank >= min_iv_rank)
    if not iv_filter_met:
        return None

    bull_put = vertical_credit_spread(
        underlying=underlying,
        contracts=contracts,
        direction="bull_put",
        current_date_str=current_date_str,
        target_delta=target_delta,
        width=width,
        target_dte=target_dte,
        max_spread_pct=max_spread_pct,
    )
    if not bull_put:
        return None

    bear_call = vertical_credit_spread(
        underlying=underlying,
        contracts=contracts,
        direction="bear_call",
        current_date_str=current_date_str,
        target_delta=target_delta,
        width=width,
        target_dte=target_dte,
        max_spread_pct=max_spread_pct,
    )
    if not bear_call:
        return None

    net_credit = bull_put["net_credit"] + bear_call["net_credit"]
    max_loss = max(bull_put["width"], bear_call["width"]) - net_credit
    max_profit = net_credit
    breakevens = [bull_put["breakeven"], bear_call["breakeven"]]
    net_delta = bull_put["net_delta"] + bear_call["net_delta"]

    return {
        "structure": f"{underlying}_iron_condor",
        "underlying": underlying,
        "expiration_date": bull_put["expiration_date"],
        "bull_put_spread": bull_put,
        "bear_call_spread": bear_call,
        "net_credit": round(net_credit, 4),
        "max_loss": round(max_loss, 4),
        "max_profit": round(max_profit, 4),
        "breakevens": [round(b, 4) for b in breakevens],
        "net_delta": round(net_delta, 4),
        "iv_rank_filter_met": iv_filter_met,
    }

