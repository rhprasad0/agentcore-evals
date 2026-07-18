"""Tests for the Week 8 projection-to-Case adapter."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from strands_evals.evaluators import Contains

from evals.adapters.cases import (
    CaseAdapterError,
    build_projection_cases,
    build_projection_experiment,
)
from src.dataset_projection import DatasetProjectionError, load_projection
from src.tool_calling_dataset import ValidationIssue


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTION_PATH = REPO_ROOT / "datasets/projections/weather-only-62.json"


class Week08CaseAdapterTests(unittest.TestCase):
    def test_valid_projection_maps_all_rows_in_source_order(self) -> None:
        projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)

        cases = build_projection_cases(
            PROJECTION_PATH,
            repo_root=REPO_ROOT,
        )

        self.assertEqual(62, len(cases))
        self.assertEqual(
            [row["exampleId"] for row in projection.rows],
            [case.name for case in cases],
        )
        self.assertEqual(
            [row["prompt"] for row in projection.rows],
            [case.input for case in cases],
        )
        self.assertEqual(
            [
                f"datasets.weather_only@1.0.0:{row['exampleId']}"
                for row in projection.rows
            ],
            [case.session_id for case in cases],
        )

    def test_cases_preserve_gate_inputs_and_exact_version_joins(self) -> None:
        projection = load_projection(PROJECTION_PATH, repo_root=REPO_ROOT)

        cases = build_projection_cases(
            PROJECTION_PATH,
            repo_root=REPO_ROOT,
        )

        for row, case in zip(projection.rows, cases, strict=True):
            with self.subTest(example_id=row["exampleId"]):
                self.assertEqual(
                    {
                        "expected": row["expected"],
                        "tags": row["tags"],
                        "scenarioFamily": row["scenarioFamily"],
                        "failureInjection": row["failureInjection"],
                        "rowProvenance": row["provenance"],
                        "versionBindings": {
                            "dataset": {
                                "datasetId": projection.document["source"]["datasetId"],
                                "version": projection.document["source"]["version"],
                                "schemaVersion": "1.0.0",
                                "taxonomyVersion": "1.0.0",
                            },
                            "projection": {
                                "projectionId": projection.document["projectionId"],
                                "version": projection.document["version"],
                            },
                            "agentManifest": projection.document["specimenBindings"][
                                "agentManifest"
                            ],
                            "toolContracts": projection.document["specimenBindings"][
                                "toolContracts"
                            ],
                        },
                    },
                    case.metadata,
                )

    def test_invalid_source_dataset_fails_before_projection_or_case_construction(self) -> None:
        with (
            patch("evals.adapters.cases.load_dataset", return_value=object()),
            patch(
                "evals.adapters.cases.validate_dataset",
                return_value=[ValidationIssue("tc-0001.expected", "synthetic defect")],
            ),
            patch("evals.adapters.cases.load_projection") as load_projection_mock,
            patch("evals.adapters.cases.Case") as case_mock,
        ):
            with self.assertRaisesRegex(
                CaseAdapterError,
                r"source dataset validation failed at tc-0001\.expected: synthetic defect",
            ):
                build_projection_cases(
                    PROJECTION_PATH,
                    repo_root=REPO_ROOT,
                )

        load_projection_mock.assert_not_called()
        case_mock.assert_not_called()

    def test_invalid_projection_fails_before_case_construction(self) -> None:
        document = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        document["selectedExampleIds"][-1] = "tc-9999"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "projection.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with patch("evals.adapters.cases.Case") as case_mock:
                with self.assertRaisesRegex(
                    DatasetProjectionError,
                    r"selectedExampleIds drift.*tc-0100.*tc-9999",
                ):
                    build_projection_cases(path, repo_root=REPO_ROOT)

        case_mock.assert_not_called()

    def test_duplicate_projected_id_fails_before_case_construction(self) -> None:
        document = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        document["selectedExampleIds"].append(document["selectedExampleIds"][0])
        document["expectedRowCount"] += 1
        with TemporaryDirectory() as directory:
            path = Path(directory) / "projection.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with patch("evals.adapters.cases.Case") as case_mock:
                with self.assertRaisesRegex(
                    DatasetProjectionError,
                    r"projection schema error at selectedExampleIds:.*non-unique",
                ):
                    build_projection_cases(path, repo_root=REPO_ROOT)

        case_mock.assert_not_called()

    def test_experiment_rejects_an_empty_evaluator_set(self) -> None:
        with patch("evals.adapters.cases.Experiment") as experiment_mock:
            with self.assertRaisesRegex(
                CaseAdapterError,
                r"at least one evaluator is required",
            ):
                build_projection_experiment(
                    PROJECTION_PATH,
                    repo_root=REPO_ROOT,
                    evaluators=[],
                )

        experiment_mock.assert_not_called()

    def test_complete_experiment_round_trip_preserves_cases_and_metadata(self) -> None:
        evaluator = Contains(value="synthetic marker")
        experiment = build_projection_experiment(
            PROJECTION_PATH,
            repo_root=REPO_ROOT,
            evaluators=[evaluator],
        )

        self.assertEqual([evaluator], experiment.evaluators)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "weather-only-62.json"
            experiment.to_file(str(path))
            restored = type(experiment).from_file(str(path))

        self.assertEqual(62, len(restored.cases))
        self.assertEqual(
            [(case.name, case.input, case.metadata) for case in experiment.cases],
            [(case.name, case.input, case.metadata) for case in restored.cases],
        )

if __name__ == "__main__":
    unittest.main()
