import unittest

from compare_wnba_props_vs_fanduel import _build_books_listing_report, _listing_fetch


class BooksListingReportTests(unittest.TestCase):
    def test_build_report_with_schedule_window(self) -> None:
        report = _build_books_listing_report(
            league="nba",
            schedule_hours=12,
            raw_counts={"Unibet": 9, "Winamax": 0},
            entries={
                "Unibet": {"status": "ok", "match_count": 2, "seconds": 1.5, "error": None},
                "Winamax": {"status": "empty", "match_count": 0, "seconds": 12.0, "error": None},
            },
        )
        self.assertEqual(report["schedule_hours"], 12)
        uni = report["books"]["Unibet"]
        self.assertEqual(uni["match_count_raw"], 9)
        self.assertEqual(uni["match_count_window"], 2)

    def test_listing_fetch_error(self) -> None:
        def boom() -> list[str]:
            raise RuntimeError("curl timeout")

        items, meta = _listing_fetch("Winamax", boom)
        self.assertEqual(items, [])
        self.assertEqual(meta["status"], "error")
        self.assertIn("timeout", meta["error"] or "")


if __name__ == "__main__":
    unittest.main()
