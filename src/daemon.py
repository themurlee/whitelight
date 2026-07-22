"""
WhiteLight Systematic Trading & Analysis Pipeline - Daemon
Background daemon script executing the systematic trading cycle every 15 minutes.
"""

import time
import subprocess
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)


def run_loop():
    print(f"[{datetime_now()}] Starting WhiteLight systematic background daemon...", flush=True)
    while True:
        try:
            print(f"[{datetime_now()}] Triggering systematic trading cycle...", flush=True)
            # Run pipeline as subprocess
            subprocess.run([sys.executable, "src/pipeline.py", "--live"], cwd=BASE_DIR)
        except Exception as e:
            print(f"[{datetime_now()}] [DAEMON ERROR] Failed to run cycle: {e}", file=sys.stderr, flush=True)
        
        print(f"[{datetime_now()}] Systematic cycle completed. Sleeping for 15 minutes (900 seconds)...", flush=True)
        time.sleep(900)


def datetime_now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


if __name__ == "__main__":
    run_loop()
