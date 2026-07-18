# Week 8 Strands Evals SDK Contract Receipt

**Verified:** 2026-07-18  
**Scope:** Root Week 8 evaluation-tool environment; no model, tool, network, or AWS API invocation was performed.

## Locked versions

The root `pyproject.toml` directly pins `strands-agents-evals`; `uv.lock` supplies the complete resolution used by the tests and CLI probes.

- `strands-agents-evals==1.0.1`
- `strands-agents==1.48.0`
- `strands-agents-tools==0.8.4`
- `pydantic==2.13.4`
- Python requirement: `>=3.10`

Week 7 captured its specimen under `strands-agents==1.46.0`. The Week 8 tooling resolution does not retarget or rewrite those completed runs: their run manifests remain attached to the versions that produced them. Week 8 evaluates canonical, provenance-linked outcomes across the repository adapter boundary.

## Installed API contract

Observed through `inspect.signature` in the locked root environment:

| Symbol | Installed contract used by Week 8 |
| --- | --- |
| `Case` | keyword-only `name`, generated `session_id`, required `input`, optional expected fields, optional `metadata` |
| `Experiment` | `Experiment(cases=None, evaluators=None, diagnosis_config=None)` |
| `Evaluator` | `Evaluator(trace_extractor=None, name=None)`; custom evaluators implement `evaluate(EvaluationData)` and return `list[EvaluationOutput]` |
| `EvaluationData` | carries input, actual/expected output and trajectory, metadata, interactions, and environment state |
| `EvaluationOutput` | required `score` and `test_pass`; optional `reason` and `label` |
| `LocalFileTaskResultStore` | initialized with a directory; `load` and `save` are keyed by case name |

Exact methods relevant to the harness:

- `LocalFileTaskResultStore.load(case_name) -> EvaluationData | None`
- `LocalFileTaskResultStore.save(case_name, result) -> None`

```text
Experiment.to_file(path)
Experiment.from_file(path, custom_evaluators=None)
Experiment.run_evaluations(task, evaluation_data_store=None)
Experiment.run_evaluations_async(task, max_workers=10, evaluation_data_store=None)
```

## Serialization compatibility probe

A synthetic `Case` carried a nested repository-shaped metadata object containing:

- an `expected` object with tool IDs, call bounds, argument constraints, and forbidden tools;
- multiple tags;
- dataset, projection, capability-manifest, and tool-contract versions.

It was serialized through `Experiment.to_file`, restored through `Experiment.from_file`, and compared recursively.

- Case count: `1`
- Evaluator count: `1` (`Contains`)
- Case name: preserved
- Nested `Case.metadata`: preserved exactly

The executable regression test is `tests/test_week_08_strands_evals_sdk_contract.py`.

## Concrete Stage B evaluator round trip

The SDK contract now has a second executable receipt: `test_stage_b_round_trip_preserves_concrete_gate_bindings` builds the provenance-validated `weather-only-62` fixture lane, serializes its 60 eligible `Case` objects and the four real custom evaluators, then restores it using the explicit evaluator registry.

- Case count: `60` canonical-trace cases; the two instrument-error receipts are excluded before `Experiment` construction.
- Evaluators: `ExpectedToolsGate`, `ArgConstraintGate`, `FailureBehaviorGate`, and `NoToolGate`.
- Case names and concrete evaluator type names: preserved across `Experiment.to_file` / `Experiment.from_file(..., custom_evaluators=...)`.

This verifies serialization/binding only. Fixture integrity is still established by `evals.fixtures.manifest.validate_fixture_manifest(...)`, and the fixture-only runtime path is exercised separately by `tests/test_week_08_harness.py`.

## CLI contract

`strands-evals --help` exposes `validate`, `report`, `diagnose`, `run`, `generate`, and `fetch`.

Observed Week 8-relevant behavior:

- `validate EXPERIMENT_FILE --custom-evaluator MODULE:CLASS` loads through `Experiment.from_file` and reports case/evaluator counts.
- `run` requires either `--agent` or `--task`, including when `--data-store` is present.
- `--data-store DIR` enables `LocalFileTaskResultStore`; a cache hit short-circuits task execution, while a cache miss runs the supplied task and saves the result.
- `--custom-evaluator MODULE:CLASS` registers custom evaluator classes before deserializing an Experiment.
- `--fail-on` accepts `any`, `none`, or `threshold:0.X`; `--exit-zero` overrides it.
- `report` reads an `EvaluationReport` JSON document and renders or rewrites it; it does not validate the repository's metric or public-safety contract.
- `Experiment(cases=..., evaluators=[])` installs one base `Evaluator` because the constructor treats an empty list like an omitted value. The repository adapter rejects an empty evaluator set instead of serializing a misleading placeholder Experiment.

A synthetic serialized Experiment passed:

```bash
uv run --locked strands-evals validate "$TMPDIR/sdk-contract.json" --json
```

Observed result: `valid: true`, one case, one `Contains` evaluator, exit code `0`.

## Architecture consequence

The SDK cache protocol is intentionally narrow: case name in, cached `EvaluationData` or null out. It has no repository experiment/projection provenance check, and its normal cache-miss behavior invokes the supplied task. Week 8 therefore keeps the SDK store behind a run-scoped repository preflight and gives PR Stage B a fixture-only `run_stage_b(...)` entry point that fails before constructing an `Experiment` on missing or invalid evidence. It does not use `strands-evals run`, a task-result store, or a cache-miss fallback. `evals.adapters.cases.build_projection_experiment` continues to require at least one evaluator.

## Claim boundary

This receipt verifies the locked package/API/CLI shape, one synthetic metadata round trip, and one concrete 60-case/four-gate serialization round trip. It does not prove the repository dataset, canonical traces, or public reports are valid; repository validators, fixture provenance checks, deterministic gates, report schemas, and offline-path tests own those claims. It also does not demonstrate managed AgentCore compatibility, current-model behavior, response quality, or production security.
