from dataclasses import dataclass
import os
import json
import numpy as np
import src.config as config
from src.storage.atomic_writer import AtomicJSONWriter

@dataclass
class RiskParams:
    max_drawdown_pct: float = 5.0
    max_position_size_pct: float = 10.0
    max_daily_loss_pct: float = 2.0
    max_correlation_to_existing: float = 0.7

class CircuitBreaker:
    def __init__(self, config_params: RiskParams = RiskParams(), baseline_account_value: float = 100000.0):
        self.config = config_params
        self.baseline = baseline_account_value
        self.locked = False
    
    def check_drawdown(self, account_value: float) -> bool:
        """Returns True if drawdown exceeds the configured limit."""
        if self.baseline <= 0:
            return False
        drawdown = (self.baseline - account_value) / self.baseline * 100.0
        if drawdown >= self.config.max_drawdown_pct:
            self.locked = True
            return True
        return False

    def check_correlation(self, ticker: str, open_tickers: list) -> float:
        """Calculate max correlation of ticker with open positions using daily bars."""
        if not open_tickers:
            return 0.0
        
        # Helper to load last 30 close prices
        def get_close_prices(t: str) -> list:
            t_dir = os.path.join(config.DATA_DIR, t)
            if not os.path.exists(t_dir):
                return []
            files = sorted([f for f in os.listdir(t_dir) if f.endswith(".jsonl")])[-30:]
            prices = []
            for f in files:
                try:
                    data = AtomicJSONWriter(os.path.join(t_dir, f)).read()
                    if data and "close" in data:
                        prices.append(float(data["close"]))
                except Exception:
                    pass
            return prices

        target_prices = get_close_prices(ticker)
        if len(target_prices) < 5:
            return 0.5  # Default correlation if data insufficient

        max_corr = 0.0
        for ot in open_tickers:
            if ot == ticker:
                return 1.0
            ot_prices = get_close_prices(ot)
            min_len = min(len(target_prices), len(ot_prices))
            if min_len >= 5:
                try:
                    c = np.corrcoef(target_prices[-min_len:], ot_prices[-min_len:])[0, 1]
                    if not np.isnan(c):
                        max_corr = max(max_corr, float(c))
                except Exception:
                    pass
        return max_corr

    def can_execute(
        self, 
        ticker: str, 
        qty: int, 
        price: float, 
        account_value: float, 
        open_tickers: list = [], 
        current_daily_loss: float = 0.0
    ) -> tuple[bool, str]:
        """Gate execution against all configured risk checks."""
        # 1. Check drawdown lockdown status
        if self.locked or self.check_drawdown(account_value):
            return False, "Circuit breaker locked due to drawdown limit breach"

        # 2. Check position size allocation cap
        order_value = qty * price
        max_alloc = account_value * (self.config.max_position_size_pct / 100.0)
        if order_value > max_alloc:
            return False, f"Order value ${order_value:.2f} exceeds max allocation limit ${max_alloc:.2f}"

        # 3. Check daily loss threshold
        max_loss = account_value * (self.config.max_daily_loss_pct / 100.0)
        if current_daily_loss > max_loss:
            return False, f"Current daily loss ${current_daily_loss:.2f} exceeds threshold ${max_loss:.2f}"

        # 4. Check correlation safety threshold
        max_corr = self.check_correlation(ticker, open_tickers)
        if max_corr > self.config.max_correlation_to_existing:
            return False, f"Max correlation with open positions ({max_corr:.2f}) exceeds limit ({self.config.max_correlation_to_existing})"

        return True, "Passed all risk validations"
