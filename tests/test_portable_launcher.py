import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.portable.launch_portable import _existing_app_instance_pid, _parse_lock_pid


class PortableLauncherTests(unittest.TestCase):
    def test_parse_lock_pid_supports_process_identity_format(self):
        self.assertEqual(_parse_lock_pid("6736|12345"), 6736)
        self.assertEqual(_parse_lock_pid("6736"), 6736)
        self.assertEqual(_parse_lock_pid(""), 0)
        self.assertEqual(_parse_lock_pid("bad|123"), 0)

    def test_existing_app_instance_pid_reads_identity_lock_file(self):
        home_root = Path(__file__).resolve().parents[1] / "runtime_test_home"
        lock_path = home_root / "data" / "app_instance.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_path.write_text("6736|12345", encoding="utf-8")
            with patch("scripts.portable.launch_portable.pid_exists", return_value=True):
                self.assertEqual(_existing_app_instance_pid(home_root), 6736)
        finally:
            if lock_path.exists():
                lock_path.unlink()
            data_dir = lock_path.parent
            if data_dir.exists():
                data_dir.rmdir()
            if home_root.exists():
                home_root.rmdir()


if __name__ == "__main__":
    unittest.main()
