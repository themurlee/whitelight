import os
import tempfile
import pytest
from src.monitoring.metrics_exporter import MetricsExporter

def test_metrics_export():
    with tempfile.NamedTemporaryFile(suffix=".prom", delete=False) as tmp:
        filepath = tmp.name

    try:
        exporter = MetricsExporter(filepath=filepath)
        exporter.export_metrics(
            account_value=105234.56,
            open_pnl=-250.0,
            closed_pnl=1240.50,
            win_rate=0.6428
        )
        
        with open(filepath, "r") as f:
            content = f.read()
            
        assert "whitelight_account_value 105234.56" in content
        assert "whitelight_open_pnl -250.00" in content
        assert "whitelight_closed_pnl 1240.50" in content
        assert "whitelight_win_rate 0.6428" in content
        
        assert "# HELP whitelight_account_value" in content
        assert "# TYPE whitelight_account_value gauge" in content

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
