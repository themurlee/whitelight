import pytest
from src.risk.position_sizer import get_vix_adjusted_quantity

def test_vix_sizing_normal():
    assert get_vix_adjusted_quantity(100, vix=15.0) == 100
    assert get_vix_adjusted_quantity(100, vix=20.0) == 100

def test_vix_sizing_elevated():
    assert get_vix_adjusted_quantity(100, vix=30.0) == 75

def test_vix_sizing_extreme():
    assert get_vix_adjusted_quantity(100, vix=40.0) == 50
    assert get_vix_adjusted_quantity(100, vix=50.0) == 50
