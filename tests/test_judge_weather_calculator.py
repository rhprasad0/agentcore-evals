"""Contract tests for the bounded Week 10 custom judge."""

from __future__ import annotations

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.judge_weather_calculator import (
    HELDOUT_EXAMPLE_IDS,
    JUDGE_MODEL_ID,
    JudgeInputError,
    judge_case,
    load_frozen_calibration_receipt,
    load_calibration_vectors,
    prompt_digest,
    run_dry_run,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class JudgeCalibrationTests(unittest.TestCase):
    def test_calibration_vectors_are_six_balanced_and_disjoint_from_heldout(self) -> None:
        vectors = load_calibration_vectors(
            REPO_ROOT / "datasets/labels/week-10-judge-calibration.jsonl"
        )

        self.assertEqual([f"cal-{index:02}" for index in range(1, 7)], [v.vector_id for v in vectors])
        self.assertTrue({v.source_example_id for v in vectors}.isdisjoint(HELDOUT_EXAMPLE_IDS))
        self.assertEqual({"pass", "fail"}, {v.expected_label for v in vectors})
        self.assertEqual(3, sum(v.expected_label == "pass" for v in vectors))
        self.assertEqual(3, sum(v.expected_label == "fail" for v in vectors))

    def test_dry_run_accounts_for_all_eight_without_a_provider(self) -> None:
        receipt = run_dry_run(REPO_ROOT)

        self.assertEqual([f"slice-{index:02}" for index in range(1, 7)], receipt["eligibleCaseIds"])
        self.assertEqual(["slice-07", "slice-08"], receipt["excludedCaseIds"])
        self.assertFalse(receipt["providerTouched"])

    def test_boundary_case_is_rejected_before_provider_is_called(self) -> None:
        touched = False

        def provider(_: str) -> dict[str, object]:
            nonlocal touched
            touched = True
            return {}

        with self.assertRaisesRegex(JudgeInputError, "not eligible"):
            judge_case(case_id="slice-07", expected={}, evidence={}, provider=provider)
        self.assertFalse(touched)

    def test_frozen_calibration_receipt_requires_complete_agreement(self) -> None:
        receipt = {
            "modelId": JUDGE_MODEL_ID,
            "promptSha256": prompt_digest(),
            "outcomes": [{"vectorId": f"cal-{index:02}", "match": True} for index in range(1, 7)],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(receipt, load_frozen_calibration_receipt(path))

            receipt["outcomes"][5]["match"] = False
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(JudgeInputError, "passed"):
                load_frozen_calibration_receipt(path)

            receipt["outcomes"][5]["match"] = True
            receipt["outcomes"][5]["vectorId"] = "cal-99"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(JudgeInputError, "passed"):
                load_frozen_calibration_receipt(path)


if __name__ == "__main__":
    unittest.main()
