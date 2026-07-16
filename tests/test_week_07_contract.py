"""Tests for the checked-in Week 7 curriculum contract."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEEK_07 = REPO_ROOT / "docs/weeks/week-07-specimen.md"


class Week07ContractTests(unittest.TestCase):
    def test_week_07_names_the_weather_only_projection_and_62_trace_gate(self) -> None:
        text = WEEK_07.read_text(encoding="utf-8")

        self.assertIn("weather-only-62@1.0.0", text)
        self.assertIn("62/62", text)
        self.assertNotIn("100/100 traces", text)


if __name__ == "__main__":
    unittest.main()
