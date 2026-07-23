import os
import tempfile
import threading
import time
import fcntl
from src.storage.atomic_writer import AtomicJSONWriter

def test_atomic_writer_concurrent():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        filepath = tmp.name

    try:
        writer = AtomicJSONWriter(filepath, lock_timeout_sec=10.0)
        writer.write({"count": 0})
        
        num_threads = 10
        num_writes = 50
        errors = []

        def worker():
            for _ in range(num_writes):
                try:
                    with writer.lock(fcntl.LOCK_EX):
                        data = writer.read_locked()
                        data["count"] += 1
                        time.sleep(0.001)
                        writer.write_locked(data)
                except Exception as e:
                    errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent write errors: {errors}"
        
        final_data = writer.read()
        assert final_data["count"] == num_threads * num_writes, f"Expected {num_threads * num_writes}, got {final_data['count']}"
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
        lock_file = filepath + ".lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)
