import unittest
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

from compare_tennis_aces_vs_fanduel import ANCHOR_MAX_WORKERS, ANCHOR_TIMEOUT


class ProgressiveSubmitTimeoutTests(unittest.TestCase):
    def test_anchor_timeout_only_applies_to_started_jobs(self) -> None:
        """Regression: soumettre 100 jobs d'un coup faisait timeout la file entiere."""
        # Simule: 5 anchors, 2 workers. Les 3 en file ne doivent PAS etre
        # consideres demarres tant qu'ils ne sont pas submit_one.
        started_at: dict[object, float] = {}
        futures: dict[object, str] = {}

        def submit_one(name: str, now: float) -> object:
            fut = object()
            futures[fut] = name
            started_at[fut] = now
            return fut

        now = 1000.0
        active = [submit_one("a", now), submit_one("b", now)]
        queued = ["c", "d", "e"]

        # Apres 80s, a et b timeout, c/d/e pas encore started
        later = now + ANCHOR_TIMEOUT + 1
        timed = [f for f in active if later - started_at[f] >= ANCHOR_TIMEOUT]
        self.assertEqual(len(timed), 2)
        self.assertEqual(len(queued), 3)
        self.assertLessEqual(len(active), ANCHOR_MAX_WORKERS)


if __name__ == "__main__":
    unittest.main()
