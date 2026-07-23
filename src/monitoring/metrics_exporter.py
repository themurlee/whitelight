import os
import tempfile
import src.config as config

class MetricsExporter:
    def __init__(self, filepath: str = None):
        self.filepath = filepath or os.path.join(config.DATA_DIR, "metrics.prom")
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def export_metrics(self, account_value: float, open_pnl: float, closed_pnl: float, win_rate: float):
        """Write account and P&L metrics in standard Prometheus text format atomically."""
        lines = [
            "# HELP whitelight_account_value Current portfolio account value",
            "# TYPE whitelight_account_value gauge",
            f"whitelight_account_value {account_value:.2f}",
            "# HELP whitelight_open_pnl Un-realized open leg profit and loss",
            "# TYPE whitelight_open_pnl gauge",
            f"whitelight_open_pnl {open_pnl:.2f}",
            "# HELP whitelight_closed_pnl Realized completed trades profit and loss",
            "# TYPE whitelight_closed_pnl gauge",
            f"whitelight_closed_pnl {closed_pnl:.2f}",
            "# HELP whitelight_win_rate Completed winning trades ratio",
            "# TYPE whitelight_win_rate gauge",
            f"whitelight_win_rate {win_rate:.4f}"
        ]
        
        dir_name = os.path.dirname(self.filepath) or "."
        with tempfile.NamedTemporaryFile(dir=dir_name, mode="w", delete=False) as tmp_f:
            tmp_f.write("\n".join(lines) + "\n")
            tmp_path = tmp_f.name
            
        try:
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e
