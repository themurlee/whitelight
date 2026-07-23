import os
import time
import shutil
import threading
from unittest.mock import patch, MagicMock
import src.config as config
from src.storage.atomic_writer import AtomicJSONWriter
from src.signal_generator import run_signal_generation
from src.executor import execute_signal

def test_race_condition_signal_executor():
    temp_data_dir = os.path.abspath("./test_race_data")
    os.makedirs(temp_data_dir, exist_ok=True)
    
    ticker = "SPY"
    ticker_dir = os.path.join(temp_data_dir, ticker)
    os.makedirs(ticker_dir, exist_ok=True)

    writer_paths = []
    for i in range(30):
        fpath = os.path.join(ticker_dir, f"2026-07-{i+1:02d}.jsonl")
        writer_paths.append(fpath)
        writer = AtomicJSONWriter(fpath)
        writer.write({
            "timestamp": f"2026-07-{i+1:02d}T00:00:00Z",
            "close": 200.0 + i,
            "open": 200.0 + i,
            "high": 205.0 + i,
            "low": 195.0 + i,
            "volume": 100000,
            "vwap": 200.0 + i
        })

    original_data_dir = config.DATA_DIR
    config.DATA_DIR = temp_data_dir

    try:
        errors = []
        stop_event = threading.Event()

        def mock_ingest():
            idx = 0
            while not stop_event.is_set():
                try:
                    fpath = writer_paths[idx % len(writer_paths)]
                    writer = AtomicJSONWriter(fpath)
                    data = writer.read()
                    if data:
                        data["close"] = float(data["close"]) + 0.01
                        writer.write(data)
                except Exception as e:
                    errors.append(f"Ingest error: {e}")
                idx += 1
                time.sleep(0.001)

        def mock_signal():
            while not stop_event.is_set():
                try:
                    run_signal_generation(ticker)
                except Exception as e:
                    errors.append(f"Signal error: {e}")
                time.sleep(0.001)

        def mock_executor():
            mock_client = MagicMock()
            mock_client.get_open_position.side_effect = Exception("No position")
            mock_client.get_orders.return_value = []
            
            with patch("src.executor.TradingClient", return_value=mock_client):
                while not stop_event.is_set():
                    try:
                        execute_signal()
                    except Exception as e:
                        errors.append(f"Executor error: {e}")
                    time.sleep(0.001)

        t1 = threading.Thread(target=mock_ingest)
        t2 = threading.Thread(target=mock_signal)
        t3 = threading.Thread(target=mock_executor)

        t1.start()
        t2.start()
        t3.start()

        time.sleep(2.0)
        stop_event.set()

        t1.join()
        t2.join()
        t3.join()

        assert not errors, f"Race condition errors encountered: {errors}"

    finally:
        config.DATA_DIR = original_data_dir
        if os.path.exists(temp_data_dir):
            shutil.rmtree(temp_data_dir)
