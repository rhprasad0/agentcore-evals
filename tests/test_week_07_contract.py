"""Tests for the checked-in Week 7 curriculum contract."""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEEK_07 = REPO_ROOT / "docs/weeks/week-07-specimen.md"
FULL_PROJECTION_REPORT = REPO_ROOT / "docs/reports/week-07-full-projection.md"
ERRATA = REPO_ROOT / "docs/errata/week-07-dataset-errata.md"


class Week07ContractTests(unittest.TestCase):
    def test_week_07_names_the_weather_only_projection_and_62_trace_gate(self) -> None:
        text = WEEK_07.read_text(encoding="utf-8")

        self.assertIn("weather-only-62@1.0.0", text)
        self.assertIn("62/62", text)
        self.assertNotIn("100/100 traces", text)

    def test_week_07_closeout_is_public_safe_and_records_frozen_review(self) -> None:
        week = WEEK_07.read_text(encoding="utf-8")
        report = FULL_PROJECTION_REPORT.read_text(encoding="utf-8")
        errata = ERRATA.read_text(encoding="utf-8")

        self.assertIn("60 canonical traces plus 2 explicit instrument errors", week)
        self.assertIn("60 of 60 comparable canonical projections matched", report)
        self.assertIn(
            "Eight rows passed, one exposed an agent behavior defect, and one exposed a contract ambiguity",
            errata,
        )
        for text in (report, errata):
            self.assertNotIn("/home/", text)
            self.assertIsNone(
                re.search(
                    r"\b[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
                    text,
                )
            )


if __name__ == "__main__":
    unittest.main()
