"""
WhiteLight Systematic Trading & Analysis Pipeline - Options Chain Selector
Filters available options contracts from the Robinhood MCP data structures
based on target Days to Expiration (DTE) and target Delta parameters.
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
