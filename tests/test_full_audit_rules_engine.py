from src.options.full_audit.rules_engine import evaluate_rules

def _contract(strike=700, bid=1.0, ask=1.1, oi=1000, delta=0.45):
    return {"strike": strike, "bid": bid, "ask": ask, "midpoint": (bid + ask) / 2.0,
            "open_interest": oi, "greeks": {"delta": delta}}

def test_evaluate_rules_all_pass():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=10)
    assert result["pass"] is True
    assert result["reason"] == "All rules passed"
    assert len(result["checks"]) == 5

def test_evaluate_rules_fails_on_low_liquidity():
    result = evaluate_rules(_contract(oi=100), iv_rank=30.0, dte=10)
    assert result["pass"] is False
    assert "iquidity" in result["reason"] or "Open Interest" in result["reason"]

def test_evaluate_rules_fails_on_min_dte():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=0)
    assert result["pass"] is False
    assert "DTE" in result["reason"]

def test_evaluate_rules_fails_on_low_delta():
    result = evaluate_rules(_contract(delta=0.10), iv_rank=30.0, dte=10)
    assert result["pass"] is False
    assert "Delta" in result["reason"]

def test_evaluate_rules_fails_on_position_sizing():
    result = evaluate_rules(_contract(), iv_rank=30.0, dte=10, account_equity=10000.0, order_value=5000.0)
    assert result["pass"] is False
    assert "allocation" in result["reason"].lower() or "sizing" in result["reason"].lower()
