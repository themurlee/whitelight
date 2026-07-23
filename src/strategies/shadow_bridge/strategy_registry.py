import os
import sys
import glob
import logging
import importlib
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("StrategyRegistry")

class StrategyRegistry:
    """Dynamically load and manage Shadow strategies as libraries."""
    
    def __init__(self, shadow_repo_path: str):
        self.shadow_path = shadow_repo_path
        self._register_shadow_path()
        self.strategies: Dict[str, type] = {}
    
    def _register_shadow_path(self):
        """Add Shadow repo to sys.path for imports."""
        if self.shadow_path not in sys.path:
            sys.path.insert(0, self.shadow_path)
            
    def load_all_strategies(self) -> Dict[str, type]:
        """
        Dynamically import all strategies from atlas/strategy_lab/strategies/*.py
        
        Returns:
        {
            "vrp_short_straddle": <Strategy class>,
            "managed_strangle": <Strategy class>,
            ...
        }
        """
        strategies_dir = os.path.join(self.shadow_path, "atlas", "strategy_lab", "strategies")
        if not os.path.exists(strategies_dir):
            logger.warning(f"Strategies directory {strategies_dir} does not exist.")
            return {}

        strategy_files = glob.glob(os.path.join(strategies_dir, "*.py"))
        
        for fpath in strategy_files:
            fname = os.path.basename(fpath).replace(".py", "")
            if fname in ("__init__", "strategy", "registry", "model", "verdicts", "settlement", "exposure", "grading", "carisk", "hub"):
                continue
            
            try:
                # Import module
                module = importlib.import_module(f"atlas.strategy_lab.strategies.{fname}")
                
                # Find Strategy class in module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, 'scan') and 
                        hasattr(attr, 'manage')):
                        self.strategies[fname] = attr
                        logger.info(f"Loaded strategy: {fname}")
                        break
            except Exception as e:
                logger.warning(f"Failed to load strategy {fname}: {e}")
        
        return self.strategies
    
    def scan_all_strategies(self, market_data: dict, current_time: float = None) -> List[Dict]:
        """
        Run .scan() on all loaded strategies in parallel.
        
        Args:
            market_data: {symbol: {open, high, low, close, volume, iv_rank, ...}}
        
        Returns:
        [
            {
                "strategy_id": "vrp_short_straddle",
                "symbol": "SPY",
                "signal": "ENTRY",
                "confidence": 0.78,
                "proposed_combo": ProposedCombo object,
                "scan_error": None,
            },
            ...
        ]
        """
        results = []
        from datetime import datetime, timezone
        
        # Build standard StrategyContext mock/adapter
        # Hub is market data provider
        class MockHub:
            def __init__(self, data):
                self.data = data
            def ref_price(self, sym):
                return self.data.get(sym, {}).get("close", 0.0)
            def daily_history(self, sym, days=30):
                # Return lists of DailyBar or simple objects
                from dataclasses import dataclass
                @dataclass
                class Bar:
                    ts: str
                    close: float
                
                # Retrieve from data dir
                import src.config as wl_config
                t_dir = os.path.join(wl_config.DATA_DIR, sym)
                if not os.path.exists(t_dir):
                    return []
                files = sorted([f for f in os.listdir(t_dir) if f.endswith(".jsonl")])[-days:]
                bars = []
                for f in files:
                    try:
                        from src.storage.atomic_writer import AtomicJSONWriter
                        data_cell = AtomicJSONWriter(os.path.join(t_dir, f)).read()
                        if data_cell and "close" in data_cell:
                            ts = data_cell.get("timestamp", f.replace(".jsonl", ""))
                            bars.append(Bar(ts=ts, close=float(data_cell["close"])))
                    except Exception:
                        pass
                return bars
            def expirations(self, sym):
                return []
            def chain(self, sym, exp):
                return []
            def row_greeks(self, **kwargs):
                return {}

        now_val = current_time or datetime.now(timezone.utc).timestamp()
        dt_val = datetime.fromtimestamp(now_val, timezone.utc)
        
        # Calculate session time (minutes since midnight ET)
        import pytz
        et_tz = pytz.timezone("US/Eastern")
        dt_et = dt_val.astimezone(et_tz)
        minute_et = dt_et.hour * 60 + dt_et.minute
        
        from atlas.strategy_lab.strategy import StrategyContext
        ctx = StrategyContext(
            now_ts=now_val,
            dt_et=dt_et,
            day=dt_et.strftime("%Y-%m-%d"),
            minute=minute_et,
            session_close_min=16*60, # 4 PM ET
            hub=MockHub(market_data),
            events=[],
            in_blackout="",
            earnings={},
            journal=None,
            open_positions=[]
        )
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for strategy_id, StrategyClass in self.strategies.items():
                try:
                    strategy_instance = StrategyClass()
                    future = executor.submit(
                        self._run_strategy_scan,
                        strategy_id,
                        strategy_instance,
                        ctx
                    )
                    futures[future] = strategy_id
                except Exception as e:
                    logger.error(f"Failed to instantiate/submit {strategy_id}: {e}")
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        return results
    
    def _run_strategy_scan(
        self,
        strategy_id: str,
        strategy: Any,
        ctx: Any
    ) -> Dict:
        """Execute strategy.scan() with error handling."""
        try:
            signals = strategy.scan(ctx)
            if not signals:
                return {
                    "strategy_id": strategy_id,
                    "signal": "HOLD",
                    "proposed_combo": None,
                    "scan_error": None
                }
            
            if isinstance(signals, list) and len(signals) > 0:
                signal = signals[0]
                return {
                    "strategy_id": strategy_id,
                    "symbol": signal.underlying,
                    "signal": "ENTRY",
                    "confidence": signal.signal.get("confidence", 0.75) if hasattr(signal, 'signal') and isinstance(signal.signal, dict) else 0.75,
                    "proposed_combo": signal,
                    "scan_error": None
                }
            
            return {
                "strategy_id": strategy_id,
                "signal": "HOLD",
                "proposed_combo": None,
                "scan_error": None
            }
        except Exception as e:
            logger.error(f"Scan failed for {strategy_id}: {e}")
            return {
                "strategy_id": strategy_id,
                "signal": "HOLD",
                "proposed_combo": None,
                "scan_error": str(e)
            }
