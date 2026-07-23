import pytest
from unittest.mock import patch, MagicMock
from src.options.audit_engine import audit_options_trade, get_contracts_for_expiry

def test_get_contracts_for_expiry_fallback():
    # Test that get_contracts_for_expiry returns valid contract dictionary chains
    # even when Alpaca client fails or is unconfigured.
    contracts = get_contracts_for_expiry("AAPL", "2026-07-24", 230.0)
    assert len(contracts) > 0
    first_contract = contracts[0]
    assert "symbol" in first_contract
    assert "strike" in first_contract
    assert "bid" in first_contract
    assert "greeks" in first_contract
    assert "delta" in first_contract["greeks"]

@patch("src.options.audit_engine.fetch_intraday_5min_candles")
@patch("src.options.audit_engine.calculate_intraday_signals")
def test_audit_options_trade_bullish_low_iv(mock_signals, mock_candles):
    # Mock technical stock indicators: Bullish bias & Low IV (RSI = 40, IV = 20)
    import pandas as pd
    df_mock = pd.DataFrame({"close": [230.0]})
    mock_candles.return_value = df_mock
    mock_signals.return_value = {
        "intraday_bias": "STRONG_BULLISH",
        "rsi_7": 40.0,
        "iv_rank": 20.0
    }
    
    result = audit_options_trade("AAPL", "2026-07-24")
    
    assert result["success"] is True
    assert result["ticker"] == "AAPL"
    assert result["current_price"] == 230.0
    assert result["signals"]["intraday_bias"] == "STRONG_BULLISH"
    assert result["signals"]["iv_rank"] == 20.0
    
    # Check that alternatives are populated and ranked by PoP descending
    alts = result["ranked_alternatives"]
    assert len(alts) > 0
    
    # Verify descending probability of profit sorting
    pops = [a["probability_of_profit"] for a in alts]
    assert pops == sorted(pops, reverse=True)
    
    # Low IV + Bullish should suit Cash Secured Puts / Spread options well
    assert "SHORT PUT" in result["primary_recommendation"] or "LONG CALL" in result["primary_recommendation"]

@patch("src.options.audit_engine.fetch_intraday_5min_candles")
@patch("src.options.audit_engine.calculate_intraday_signals")
def test_audit_options_trade_bearish_high_iv(mock_signals, mock_candles):
    # Mock technical stock indicators: Bearish bias & High IV (RSI = 75, IV = 65)
    import pandas as pd
    df_mock = pd.DataFrame({"close": [230.0]})
    mock_candles.return_value = df_mock
    mock_signals.return_value = {
        "intraday_bias": "STRONG_BEARISH",
        "rsi_7": 75.0,
        "iv_rank": 65.0
    }
    
    result = audit_options_trade("AAPL", "WEEKLY")
    
    assert result["success"] is True
    assert result["signals"]["intraday_bias"] == "STRONG_BEARISH"
    assert result["signals"]["iv_rank"] == 65.0
    
    alts = result["ranked_alternatives"]
    # High IV Bearish should recommend Bear Call Credit Spread
    assert "BEAR CALL SPREAD" in result["primary_recommendation"]
