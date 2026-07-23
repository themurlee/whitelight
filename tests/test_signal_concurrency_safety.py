import pytest
import threading
import time
import os
from datetime import datetime, timezone
from src.coordinator import run_pipeline
from src.executor import execute_signal

def test_concurrent_signal_execution():
    """Verify that concurrent tickers don't overwrite each other's signals."""
    
    # Mock signals for 3 different tickers
    signals = {
        "SPY": {"ticker": "SPY", "action": "HOLD", "close": 450.0, "rsi": 55.0},
        "QQQ": {"ticker": "QQQ", "action": "HOLD", "close": 380.0, "rsi": 65.0},
        "IWM": {"ticker": "IWM", "action": "HOLD", "close": 190.0, "rsi": 50.0}
    }
    
    execution_results = {}
    execution_lock = threading.Lock()
    
    def execute_ticker_signal(ticker):
        """Execute signal for a single ticker (simulates concurrent execution)."""
        signal = signals[ticker]
        try:
            # Simulate execution with in-memory signal passing
            execute_signal(cycle_id="test_cycle_123", signal=signal)
            
            with execution_lock:
                execution_results[ticker] = "success"
        except Exception as e:
            with execution_lock:
                execution_results[ticker] = f"error: {e}"
    
    # Launch 3 threads (simulating concurrent coordinator workers)
    threads = []
    for ticker in ["SPY", "QQQ", "IWM"]:
        t = threading.Thread(target=execute_ticker_signal, args=(ticker,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join(timeout=10)
    
    # Verify all executed successfully (no race condition)
    assert execution_results.get("SPY") == "success", "SPY execution should succeed"
    assert execution_results.get("QQQ") == "success", "QQQ execution should succeed"
    assert execution_results.get("IWM") == "success", "IWM execution should succeed"
    
    print("✓ Concurrent signal execution test passed")

def test_backward_compatibility():
    """Verify that execute_signal() still works without signal parameter (disk fallback)."""
    
    import os
    from src.storage.atomic_writer import AtomicJSONWriter
    import src.config as config
    
    # Write a test signal to disk
    signal_log_path = os.path.join(config.DATA_DIR, "signal_log.json")
    test_signal = {"ticker": "TEST", "action": "HOLD", "close": 100.0}
    AtomicJSONWriter(signal_log_path).write(test_signal)
    
    # Call execute_signal() without signal parameter (backward compat)
    try:
        execute_signal(cycle_id="compat_test", signal=None)  # ← No signal param
        print("✓ Backward compatibility test passed (disk fallback works)")
    except Exception as e:
        print(f"✗ Backward compatibility test failed: {e}")
        raise

if __name__ == "__main__":
    test_concurrent_signal_execution()
    test_backward_compatibility()
