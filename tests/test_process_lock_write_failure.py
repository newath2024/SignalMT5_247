import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infra.process_lock import ProcessFileLock


class ProcessLockWriteFailureTests(unittest.TestCase):
    def test_acquire_closes_handle_and_returns_false_when_write_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "app.lock"
            lock = ProcessFileLock(lock_path)

            with patch("infra.process_lock.os.write", side_effect=OSError("disk full")):
                acquired = lock.acquire()

            self.assertFalse(acquired)
            self.assertFalse(lock_path.exists())
            self.assertIsNone(lock._handle)


if __name__ == "__main__":
    unittest.main()
