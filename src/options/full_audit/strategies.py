from typing import List, Dict


def _nearest_level_reference(strike: float, levels: Dict) -> str:
    all_levels = levels.get("levels_below", []) + levels.get("levels_above", [])
    if not all_levels:
        return None
    nearest = min(all_levels, key=lambda l: abs(l - strike))
    if abs(nearest - strike) > (strike * 0.02):
        return None
    side = "resistance" if nearest in levels.get("levels_above", []) else "support"
    return f"near {side} ${nearest:.2f}"


def build_strategy_cards(
    ticker: str, expiration: str, dte: int, current_price: float,
    contracts: List[Dict], bias: str, iv_rank: float, levels: Dict,
) -> List[Dict]:
    """Generate ranked strategy cards for one expiry, anchored to the given price levels."""
    high_iv = iv_rank > 50.0
    direction = "BULLISH" if "BULLISH" in bias else ("BEARISH" if "BEARISH" in bias else "NEUTRAL")

    calls = sorted([c for c in contracts if c["type"] == "CALL"], key=lambda x: x["strike"])
    puts = sorted([c for c in contracts if c["type"] == "PUT"], key=lambda x: x["strike"])
    if not calls:
        return []

    atm_call = min(calls, key=lambda x: abs(x["strike"] - current_price))
    atm_put = min(puts, key=lambda x: abs(x["strike"] - current_price)) if puts else None
    otm_calls = [c for c in calls if c["strike"] > current_price]
    otm_call = otm_calls[0] if otm_calls else atm_call
    itm_calls = [c for c in calls if c["strike"] < current_price]
    itm_call = itm_calls[-1] if itm_calls else atm_call

    cards = []

    if direction in ("BULLISH", "NEUTRAL") and atm_put:
        put_delta = abs(atm_put["greeks"].get("delta", 0.50))
        pop = min(round((1.0 - put_delta + 0.10) * 100, 1), 85.0)
        cards.append({
            "strategy": "SHORT PUT (Cash Secured Put)",
            "description": f"Sell to Open {ticker} ${atm_put['strike']} PUT @ ${atm_put['midpoint']:.2f}",
            "strike": atm_put["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if high_iv else "MEDIUM",
            "greeks": atm_put["greeks"], "level_reference": _nearest_level_reference(atm_put["strike"], levels),
            "midpoint": atm_put["midpoint"], "open_interest": atm_put["open_interest"],
        })

    if direction == "BULLISH":
        call_delta = abs(atm_call["greeks"].get("delta", 0.50))
        pop = max(round((call_delta - 0.10) * 100, 1), 30.0)
        cards.append({
            "strategy": "LONG CALL",
            "description": f"Buy to Open {ticker} ${atm_call['strike']} CALL @ ${atm_call['midpoint']:.2f}",
            "strike": atm_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if not high_iv else "LOW",
            "greeks": atm_call["greeks"], "level_reference": _nearest_level_reference(atm_call["strike"], levels),
            "midpoint": atm_call["midpoint"], "open_interest": atm_call["open_interest"],
        })

    if direction == "BULLISH" and dte >= 90:
        net_debit = max(1.0, itm_call["midpoint"] - otm_call["midpoint"])
        cards.append({
            "strategy": "POOR MAN'S COVERED CALL (PMCC)",
            "description": f"Buy deep ITM ${itm_call['strike']} Call, Sell OTM ${otm_call['strike']} Call",
            "strike": itm_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": 72.5, "suitability": "HIGH" if not high_iv else "MEDIUM",
            "greeks": itm_call["greeks"], "level_reference": _nearest_level_reference(otm_call["strike"], levels),
            "midpoint": itm_call["midpoint"], "open_interest": itm_call["open_interest"],
        })

    if direction == "BEARISH" and atm_put:
        put_delta = abs(atm_put["greeks"].get("delta", 0.50))
        pop = max(round((put_delta - 0.10) * 100, 1), 30.0)
        cards.append({
            "strategy": "LONG PUT",
            "description": f"Buy to Open {ticker} ${atm_put['strike']} PUT @ ${atm_put['midpoint']:.2f}",
            "strike": atm_put["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": pop, "suitability": "HIGH" if not high_iv else "LOW",
            "greeks": atm_put["greeks"], "level_reference": _nearest_level_reference(atm_put["strike"], levels),
            "midpoint": atm_put["midpoint"], "open_interest": atm_put["open_interest"],
        })

    # New: outright LEAPS stock-replacement call, deep ITM/ATM (delta >= 0.70), LEAPS bucket only
    if dte >= 270:
        deep_itm_calls = [c for c in calls if abs(c["greeks"].get("delta", 0)) >= 0.70]
        leaps_call = deep_itm_calls[0] if deep_itm_calls else itm_call
        cards.append({
            "strategy": "LEAPS (Stock Replacement Call)",
            "description": f"Buy to Open {ticker} ${leaps_call['strike']} CALL @ ${leaps_call['midpoint']:.2f} ({dte} DTE)",
            "strike": leaps_call["strike"], "expiration": expiration, "dte": dte,
            "probability_of_profit": 68.0, "suitability": "HIGH" if not high_iv else "MEDIUM",
            "greeks": leaps_call["greeks"], "level_reference": _nearest_level_reference(leaps_call["strike"], levels),
            "midpoint": leaps_call["midpoint"], "open_interest": leaps_call["open_interest"],
        })

    return sorted(cards, key=lambda c: c["probability_of_profit"], reverse=True)
