"""Private, revisioned state for reviewing the frozen Week 7 trace sample."""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.review_sample import load_frozen_review_sample


VERDICTS = (
    "pass",
    "agent-bug",
    "dataset-bug",
    "contract-ambiguity",
    "instrument-error",
)
CONFIDENCE_LEVELS = ("high", "medium", "low")
CHECK_FIELDS = (
    "expectationDefensible",
    "toolChoiceAndCount",
    "arguments",
    "resultHandling",
    "responseRequirements",
    "noForbiddenBehavior",
)


class ReviewValidationError(ValueError):
    """A proposed human review is incomplete or malformed."""


class ReviewConflictError(RuntimeError):
    """The browser attempted to save against a stale review revision."""


class Week07ReviewWorkspace:
    """Bind frozen source rows, canonical traces, and private human decisions."""

    def __init__(
        self,
        *,
        sample_id: str,
        experiment_id: str,
        rows: tuple[dict[str, Any], ...],
        traces: Mapping[str, Mapping[str, Any]],
        review_path: Path,
    ) -> None:
        self.sample_id = sample_id
        self.experiment_id = experiment_id
        self.rows = rows
        self.traces = {example_id: dict(trace) for example_id, trace in traces.items()}
        self.review_path = review_path
        self._validate_bindings()
        self.trace_set_sha256 = self._derive_trace_set_sha256()

    def payload(self) -> dict[str, Any]:
        """Return source-ordered review material without an assistant verdict."""

        document = self._load_review_document()
        verdict_counts = Counter(
            review["verdict"] for review in document["reviews"].values()
        )
        rows = []
        for row in self.rows:
            example_id = row["exampleId"]
            trace = self.traces[example_id]
            tool_calls = [
                {
                    "sequence": span["sequence"],
                    "tool": span["tool"],
                    "observedToolName": span["observedToolName"],
                    "arguments": span["arguments"],
                    "result": span["result"],
                    "selectionReasoning": span["selectionReasoning"],
                }
                for span in trace["spans"]
                if span["operationName"] == "execute_tool"
            ]
            rows.append(
                {
                    "exampleId": example_id,
                    "scenarioFamily": row["scenarioFamily"],
                    "tags": row["tags"],
                    "prompt": row["prompt"],
                    "expected": row["expected"],
                    "failureInjection": row.get("failureInjection"),
                    "observed": {
                        "response": trace["response"],
                        "toolCalls": tool_calls,
                        "spanCount": len(trace["spans"]),
                        "tokenUsage": _root_token_usage(trace),
                    },
                    "review": document["reviews"].get(example_id),
                }
            )
        reviewed = len(document["reviews"])
        return {
            "schemaVersion": "1.0.0",
            "sampleId": self.sample_id,
            "traceSetSha256": self.trace_set_sha256,
            "revision": _document_revision(document),
            "reviewMetadata": {
                "verdicts": list(VERDICTS),
                "confidenceLevels": list(CONFIDENCE_LEVELS),
                "checkFields": list(CHECK_FIELDS),
            },
            "summary": {
                "total": len(self.rows),
                "reviewed": reviewed,
                "remaining": len(self.rows) - reviewed,
                "verdictCounts": {verdict: verdict_counts[verdict] for verdict in VERDICTS},
            },
            "rows": rows,
        }

    def save_review(
        self,
        example_id: str,
        review: Mapping[str, Any],
        *,
        revision: str,
    ) -> dict[str, Any]:
        """Validate and atomically persist one complete review decision."""

        if example_id not in {row["exampleId"] for row in self.rows}:
            raise ReviewValidationError(f"unknown frozen sample row: {example_id}")
        document = self._load_review_document()
        if revision != _document_revision(document):
            raise ReviewConflictError("review state changed; reload before saving")
        validated = _validate_review(example_id, review)
        validated["reviewedAt"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        document["reviews"][example_id] = validated
        _atomic_write_json(self.review_path, document)
        return self.payload()

    def export_document(self) -> dict[str, Any]:
        """Return the complete private review document for browser download."""

        return self._load_review_document()

    def _validate_bindings(self) -> None:
        if not self.rows:
            raise ReviewValidationError("review workspace requires at least one row")
        row_ids = [row.get("exampleId") for row in self.rows]
        if len(row_ids) != len(set(row_ids)) or not all(
            isinstance(example_id, str) for example_id in row_ids
        ):
            raise ReviewValidationError("review rows require unique string example IDs")
        if set(row_ids) != set(self.traces):
            raise ReviewValidationError("review rows and canonical traces must resolve exactly")
        for row in self.rows:
            trace = self.traces[row["exampleId"]]
            if trace.get("prompt") != row.get("prompt"):
                raise ReviewValidationError(
                    f"prompt mismatch for {row['exampleId']} between dataset and trace"
                )
            if not isinstance(trace.get("spans"), list) or not isinstance(
                trace.get("response"), str
            ):
                raise ReviewValidationError(
                    f"canonical trace for {row['exampleId']} is incomplete"
                )

    def _derive_trace_set_sha256(self) -> str:
        projection = [
            {
                "exampleId": row["exampleId"],
                "trace": self.traces[row["exampleId"]],
            }
            for row in self.rows
        ]
        return sha256(_canonical_json_bytes(projection)).hexdigest()

    def _load_review_document(self) -> dict[str, Any]:
        if not self.review_path.exists():
            return {
                "schemaVersion": "1.0.0",
                "sampleId": self.sample_id,
                "experimentId": self.experiment_id,
                "traceSetSha256": self.trace_set_sha256,
                "reviews": {},
            }
        document = json.loads(self.review_path.read_text(encoding="utf-8"))
        expected_binding = (
            self.sample_id,
            self.experiment_id,
            self.trace_set_sha256,
        )
        observed_binding = (
            document.get("sampleId"),
            document.get("experimentId"),
            document.get("traceSetSha256"),
        )
        if observed_binding != expected_binding:
            raise ReviewConflictError("saved review is bound to different source evidence")
        reviews = document.get("reviews")
        if document.get("schemaVersion") != "1.0.0" or not isinstance(reviews, dict):
            raise ReviewValidationError("saved review document is malformed")
        for example_id, review in reviews.items():
            _validate_review(example_id, review, allow_reviewed_at=True)
        return document


def load_week07_review_workspace(
    repo_root: Path,
    run_directory: Path,
    *,
    review_path: Path | None = None,
) -> Week07ReviewWorkspace:
    """Load the exact frozen sample from one accepted local run directory."""

    root = repo_root.resolve()
    sample = load_frozen_review_sample(
        root / "datasets/reviews/week-07-ten-row-sample.json",
        projection_path=root / "datasets/projections/weather-only-62.json",
        repo_root=root,
    )
    manifest_path = run_directory / "run-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewValidationError(f"cannot load accepted run manifest: {error}") from error
    experiment_id = manifest.get("experimentId")
    if not isinstance(experiment_id, str):
        raise ReviewValidationError("accepted run manifest has no experimentId")
    traces = {}
    for row in sample.rows:
        trace_path = (
            run_directory
            / "cases"
            / row["exampleId"]
            / "canonical-trace.json"
        )
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReviewValidationError(
                f"cannot load canonical trace for {row['exampleId']}: {error}"
            ) from error
        if not isinstance(trace, dict):
            raise ReviewValidationError(
                f"canonical trace for {row['exampleId']} must be an object"
            )
        traces[row["exampleId"]] = trace
    return Week07ReviewWorkspace(
        sample_id=sample.document["sampleId"],
        experiment_id=experiment_id,
        rows=sample.rows,
        traces=traces,
        review_path=review_path or run_directory / "human-review.json",
    )


def _validate_review(
    example_id: str,
    review: Mapping[str, Any],
    *,
    allow_reviewed_at: bool = False,
) -> dict[str, Any]:
    expected_keys = {"exampleId", "verdict", "confidence", "checks", "notes"}
    if allow_reviewed_at:
        expected_keys.add("reviewedAt")
    if set(review) != expected_keys or review.get("exampleId") != example_id:
        raise ReviewValidationError("review fields or exampleId do not match")
    verdict = review.get("verdict")
    confidence = review.get("confidence")
    checks = review.get("checks")
    notes = review.get("notes")
    if verdict not in VERDICTS:
        raise ReviewValidationError(f"unsupported verdict: {verdict!r}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ReviewValidationError(f"unsupported confidence: {confidence!r}")
    if not isinstance(checks, Mapping) or set(checks) != set(CHECK_FIELDS):
        raise ReviewValidationError("review checks must contain the exact checklist")
    if not all(isinstance(checks[field], bool) for field in CHECK_FIELDS):
        raise ReviewValidationError("every review check must be boolean")
    if not isinstance(notes, str) or len(notes) > 5000:
        raise ReviewValidationError("review notes must be a string of at most 5000 characters")
    validated = {
        "exampleId": example_id,
        "verdict": verdict,
        "confidence": confidence,
        "checks": {field: checks[field] for field in CHECK_FIELDS},
        "notes": notes,
    }
    if allow_reviewed_at:
        reviewed_at = review.get("reviewedAt")
        if not isinstance(reviewed_at, str) or not reviewed_at.endswith("Z"):
            raise ReviewValidationError("reviewedAt must be a UTC timestamp")
        validated["reviewedAt"] = reviewed_at
    return validated


def _root_token_usage(trace: Mapping[str, Any]) -> Any:
    root = next(
        (
            span
            for span in trace["spans"]
            if span["operationName"] == "invoke_agent" and span["parentSpanId"] is None
        ),
        None,
    )
    return root.get("tokenUsage") if root is not None else None


def _document_revision(document: Mapping[str, Any]) -> str:
    return sha256(_canonical_json_bytes(document)).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            json.dump(value, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
