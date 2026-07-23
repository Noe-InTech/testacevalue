import os
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from atomic_json import write_json_atomic


class AtomicJsonTests(unittest.TestCase):
    def test_concurrent_writes_do_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"

            def write(index: int) -> None:
                write_json_atomic(path, {"n": index, "pid": os.getpid()})

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(write, range(40)))

            data = path.read_text(encoding="utf-8")
            self.assertIn('"n":', data)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
