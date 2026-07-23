import time
import unittest

from compare_tennis_aces_vs_fanduel import (
    ANCHOR_TIMEOUT,
    BOOK_STEP_TIMEOUT,
    _run_with_timeout,
    _skipped_anchor_result,
)


class AnchorTimeoutTests(unittest.TestCase):
    def test_run_with_timeout_returns_none_on_slow_call(self) -> None:
        def slow() -> str:
            time.sleep(0.4)
            return "done"

        started = time.monotonic()
        result = _run_with_timeout(slow, timeout=0.05, label="slow-test")
        elapsed = time.monotonic() - started
        self.assertIsNone(result)
        # Ne doit PAS attendre la fin du sleep(0.4) — shutdown(wait=False).
        self.assertLess(elapsed, 0.25)

    def test_run_with_timeout_returns_value(self) -> None:
        result = _run_with_timeout(lambda: 42, timeout=1.0, label="fast-test")
        self.assertEqual(result, 42)

    def test_skipped_anchor_result_shape(self) -> None:
        row = _skipped_anchor_result("A vs B", reason="timeout")
        self.assertTrue(row["skipped"])
        self.assertEqual(row["match"], "A vs B")
        self.assertEqual(row["comparable_ace_count"], 0)
        self.assertGreater(ANCHOR_TIMEOUT, BOOK_STEP_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
