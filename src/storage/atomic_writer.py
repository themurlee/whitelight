import fcntl
import tempfile
import os
import json
import time
import logging
import contextlib
import random

logger = logging.getLogger("AtomicJSONWriter")

class AtomicJSONWriter:
    def __init__(self, filepath: str, lock_timeout_sec: float = 5.0):
        self.filepath = filepath
        self.lockfile = filepath + ".lock"
        self.lock_timeout = lock_timeout_sec

    def _acquire_lock(self, lock_type: int) -> int:
        """Acquire lock on self.lockfile. Returns lock file descriptor."""
        dir_name = os.path.dirname(self.lockfile)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        fd = os.open(self.lockfile, os.O_CREAT | os.O_WRONLY, 0o666)
        
        start_time = time.time()
        delay = 0.005
        attempts = 0
        while True:
            try:
                fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                attempts += 1
                elapsed = time.time() - start_time
                if elapsed >= self.lock_timeout:
                    os.close(fd)
                    logger.warning(f"Lock contention on {self.lockfile}. Lock acquisition timed out after {elapsed:.2f}s (attempts: {attempts})")
                    raise TimeoutError(f"Lock acquisition timed out after {elapsed:.2f}s (attempts: {attempts})")
                
                # Exponential backoff with jitter
                sleep_time = min(delay * (0.5 + random.random()), self.lock_timeout - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                delay = min(delay * 2, 0.2)

    @contextlib.contextmanager
    def lock(self, lock_type: int = fcntl.LOCK_EX):
        """Context manager to hold lock over multiple operations."""
        fd = self._acquire_lock(lock_type)
        try:
            yield fd
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            os.close(fd)

    def write_locked(self, data: dict) -> bool:
        """Write dict to filepath. Assumes lock is already held by caller."""
        dir_name = os.path.dirname(self.filepath) or "."
        os.makedirs(dir_name, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(dir=dir_name, mode="w", delete=False) as tmp_f:
            json.dump(data, tmp_f, indent=2)
            tmp_path = tmp_f.name
            
        try:
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e
        return True

    def read_locked(self) -> dict:
        """Read dict from filepath. Assumes lock is already held by caller."""
        if not os.path.exists(self.filepath):
            return {}
            
        for attempt in range(3):
            try:
                with open(self.filepath, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError as jde:
                if attempt == 2:
                    raise jde
                time.sleep(0.05)
        return {}

    def write(self, data: dict) -> bool:
        """Write dict to filepath with exclusive lock, temp-file-then-rename."""
        fd = None
        try:
            fd = self._acquire_lock(fcntl.LOCK_EX)
            return self.write_locked(data)
        except Exception as e:
            logger.error(f"Failed atomic write to {self.filepath}: {e}")
            raise e
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                os.close(fd)

    def read(self) -> dict:
        """Read dict from filepath with shared lock."""
        if not os.path.exists(self.filepath):
            return {}
            
        fd = None
        try:
            fd = self._acquire_lock(fcntl.LOCK_SH)
            return self.read_locked()
        except Exception as e:
            logger.error(f"Failed locked read from {self.filepath}: {e}")
            raise e
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                os.close(fd)
