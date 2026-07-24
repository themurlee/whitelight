from src.options.full_audit.strategies import build_strategy_cards

def _mk_contract(strike, opt_type, delta):
    return {
        "symbol": f"TEST{opt_type[0]}{int(strike)}", "type": opt_type, "strike": float(strike),
        "expiration": "2026-08-15", "bid": 1.0, "ask": 1.2, "midpoint": 1.1,
        "open_interest": 1000, "greeks": {"delta": delta, "gamma": 0.02, "theta": -0.03, "vega": 0.1},
    }

def test_build_strategy_cards_bullish_low_iv_includes_long_call_and_csp():
    contracts = [
        _mk_contract(695, "PUT", -0.45),
        _mk_contract(700, "CALL", 0.50),
        _mk_contract(705, "CALL", 0.35),
    ]
    levels = {"levels_below": [685.0], "levels_above": [700.0, 705.0]}
    cards = build_strategy_cards(
        ticker="QQQ", expiration="2026-08-15", dte=23, current_price=698.0,
        contracts=contracts, bias="BULLISH", iv_rank=25.0, levels=levels,
    )
    strategies = {c["strategy"] for c in cards}
    assert "LONG CALL" in strategies
    assert "SHORT PUT (Cash Secured Put)" in strategies
    for c in cards:
        assert c["expiration"] == "2026-08-15"
        assert c["dte"] == 23
        assert 0.0 <= c["probability_of_profit"] <= 100.0

def test_build_strategy_cards_leaps_bucket_adds_leaps_strategy():
    contracts = [_mk_contract(650, "CALL", 0.78), _mk_contract(700, "CALL", 0.50)]
    levels = {"levels_below": [], "levels_above": [700.0]}
    cards = build_strategy_cards(
        ticker="QQQ", expiration="2027-06-18", dte=330, current_price=698.0,
        contracts=contracts, bias="BULLISH", iv_rank=25.0, levels=levels,
    )
    strategies = {c["strategy"] for c in cards}
    assert "LEAPS (Stock Replacement Call)" in strategies
    leaps_card = next(c for c in cards if c["strategy"] == "LEAPS (Stock Replacement Call)")
    assert leaps_card["greeks"]["delta"] >= 0.70
