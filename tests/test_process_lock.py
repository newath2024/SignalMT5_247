import unittest
from unittest.mock import patch

from infra.process_lock import ProcessFileLock, pid_exists


class ProcessLockTests(unittest.TestCase):
    @patch("infra.process_lock.os.name", "nt")
    @patch("infra.process_lock._windows_pid_visible", return_value=False)
    @patch("infra.process_lock._windows_process_creation_time", return_value=12345)
    def test_pid_exists_requires_visible_windows_process(self, _creation_mock, _visible_mock):
        self.assertFalse(pid_exists(6736))

    @patch("infra.process_lock.os.name", "nt")
    @patch("infra.process_lock._windows_pid_visible", return_value=False)
    @patch("infra.process_lock._windows_process_creation_time", return_value=12345)
    def test_identity_match_rejects_stale_invisible_windows_pid(self, _creation_mock, _visible_mock):
        lock = ProcessFileLock("dummy.lock")
        self.assertFalse(lock._identity_matches("6736|12345"))


if __name__ == "__main__":
    unittest.main()
