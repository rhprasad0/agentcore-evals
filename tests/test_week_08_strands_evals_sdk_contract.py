"""Tests for the pinned Week 8 Strands Evals SDK contract."""

from __future__ import annotations

import inspect
import subprocess
import tomllib
import unittest
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from strands_evals import Case, Experiment, LocalFileTaskResultStore
from strands_evals.evaluators import Contains, Evaluator
from strands_evals.types.evaluation import EvaluationData, EvaluationOutput

from evals.evaluators.gates import (
    ArgConstraintGate,
    ExpectedToolsGate,
    FailureBehaviorGate,
    NoToolGate,
)
from evals.harness import build_stage_b_experiment, load_stage_b_evidence


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SDK_RECEIPT = REPO_ROOT / "docs/reports/week-08-strands-evals-sdk-receipt.md"


class Week08StrandsEvalsSdkContractTests(unittest.TestCase):
    def test_root_dev_dependencies_pin_strands_evals_exactly(self) -> None:
        document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

        self.assertIn(
            "strands-agents-evals==1.0.1",
            document["dependency-groups"]["dev"],
        )

    def test_locked_sdk_exports_the_required_harness_api(self) -> None:
        self.assertEqual("1.0.1", version("strands-agents-evals"))

        signatures = {
            "Case": inspect.signature(Case),
            "Experiment": inspect.signature(Experiment),
            "Evaluator": inspect.signature(Evaluator),
            "EvaluationData": inspect.signature(EvaluationData),
            "EvaluationOutput": inspect.signature(EvaluationOutput),
            "LocalFileTaskResultStore": inspect.signature(LocalFileTaskResultStore),
        }
        required_parameters = {
            "Case": {"name", "input", "metadata"},
            "Experiment": {"cases", "evaluators"},
            "Evaluator": {"trace_extractor", "name"},
            "EvaluationData": {"input", "actual_output", "metadata"},
            "EvaluationOutput": {"score", "test_pass", "reason", "label"},
            "LocalFileTaskResultStore": {"directory"},
        }
        for symbol, required in required_parameters.items():
            with self.subTest(symbol=symbol):
                self.assertTrue(required.issubset(signatures[symbol].parameters))

        self.assertEqual(
            {"self", "task", "evaluation_data_store"},
            set(inspect.signature(Experiment.run_evaluations).parameters),
        )
        self.assertEqual(
            {"self", "task", "max_workers", "evaluation_data_store"},
            set(inspect.signature(Experiment.run_evaluations_async).parameters),
        )
        self.assertEqual(
            {"self", "case_name"},
            set(inspect.signature(LocalFileTaskResultStore.load).parameters),
        )

    def test_cli_help_exposes_the_required_stage_boundary_flags(self) -> None:
        commands = {
            "validate": {"--custom-evaluator"},
            "run": {"--task", "--data-store", "--custom-evaluator", "--fail-on"},
            "report": {"REPORTS_FILE", "--output"},
        }
        for command, required in commands.items():
            completed = subprocess.run(
                ["strands-evals", command, "--help"],
                check=True,
                capture_output=True,
                text=True,
            )
            with self.subTest(command=command):
                for value in required:
                    self.assertIn(value, completed.stdout)

    def test_experiment_round_trip_preserves_nested_case_metadata(self) -> None:
        expected_metadata = {
            "expected": {
                "toolIds": ["weather.get_current_weather"],
                "callBounds": {
                    "weather.get_current_weather": {"minCalls": 1, "maxCalls": 1}
                },
                "argConstraints": {
                    "weather.get_current_weather": {
                        "city": {"allowedValues": ["Oslo"]}
                    }
                },
                "mustNotCall": ["search.web_search"],
            },
            "tags": ["straightforward", "weather"],
            "versions": {
                "dataset": "1.0.0",
                "projection": "1.0.0",
                "capabilityManifest": "4.0.0",
                "toolContract": "2.0.0",
            },
        }
        experiment = Experiment(
            cases=[
                Case(
                    name="tc-0001",
                    input="What is the weather in Oslo?",
                    metadata=expected_metadata,
                )
            ],
            evaluators=[Contains(value="weather")],
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "week-08-experiment.json"
            experiment.to_file(str(path))
            restored = Experiment.from_file(str(path))

        self.assertEqual(1, len(restored.cases))
        self.assertEqual("tc-0001", restored.cases[0].name)
        self.assertEqual(expected_metadata, restored.cases[0].metadata)

    def test_stage_b_round_trip_preserves_concrete_gate_bindings(self) -> None:
        experiment = build_stage_b_experiment(load_stage_b_evidence(REPO_ROOT))

        with TemporaryDirectory() as directory:
            path = Path(directory) / "weather-only-stage-b.json"
            experiment.to_file(str(path))
            restored = Experiment.from_file(
                str(path),
                custom_evaluators=[
                    ExpectedToolsGate,
                    ArgConstraintGate,
                    FailureBehaviorGate,
                    NoToolGate,
                ],
            )

        self.assertEqual(60, len(restored.cases))
        self.assertEqual(
            [case.name for case in experiment.cases],
            [case.name for case in restored.cases],
        )
        self.assertEqual(
            {
                "ExpectedToolsGate",
                "ArgConstraintGate",
                "FailureBehaviorGate",
                "NoToolGate",
            },
            {type(evaluator).__name__ for evaluator in restored.evaluators},
        )

    def test_sdk_receipt_records_the_locked_contract_and_claim_boundary(self) -> None:
        text = SDK_RECEIPT.read_text(encoding="utf-8")

        for required in (
            "`strands-agents-evals==1.0.1`",
            "`strands-agents==1.48.0`",
            "Nested `Case.metadata`: preserved exactly",
            "## Concrete Stage B evaluator round trip",
            "`ExpectedToolsGate`, `ArgConstraintGate`, `FailureBehaviorGate`, and `NoToolGate`",
            "`LocalFileTaskResultStore.load(case_name) -> EvaluationData | None`",
            "`--data-store`",
            "`--fail-on`",
            "does not prove the repository dataset, canonical traces, or public reports are valid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
