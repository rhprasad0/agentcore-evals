# Deterministic mock registry

**Status:** Week 6 contract-bound mock implementation

**Artifacts:**

- [`src/deterministic_mocks.py`](../src/deterministic_mocks.py)
- [`datasets/fixtures/mocks/tool-calling.jsonl`](../datasets/fixtures/mocks/tool-calling.jsonl)
- [`tests/test_deterministic_mocks.py`](../tests/test_deterministic_mocks.py)

## Boundary and claim

The registry provides deterministic normalized tool results for schema-valid calls against the exact contracts pinned by `tool-calling-100.manifest.json`. It resolves the complete `agents.weather@3.0.0` grant set before loading fixtures and exposes exact copies of the checked-in model-visible contracts through `registered_surfaces()`.

This establishes interface equivalence at the registered contract boundary: exact name, description, input schema, normalized output schema, failure kinds, retry qualifiers, side-effect declaration, and result-trust declaration. It does **not** reproduce provider behavior, Gateway or MCP transport, authentication, latency, live-data freshness, or model determinism.

The checked-in fixture set contains one ordinary success for each exact contract, scripted normalized failures for every dataset row whose `failureInjection` is non-null, and the `tc-0092` untrusted-result fixture containing the one canonical inert canary. Later harness work may add success keys as additional rows become executable; absence is always a visible miss, never a fallback result.

## Fixture identity

Every JSONL fixture records:

- `exampleId` — the row-scoped scripted world. Row scope permits the same valid call to produce a success in one scenario and an injected failure in another without weakening the call key.
- `toolId` and `contractVersion` — the exact reviewed interface.
- `canonicalizerVersion` — the canonicalization behavior version.
- `arguments` — the readable original JSON object.
- `argumentsHash` — SHA-256 of the canonical UTF-8 argument bytes.
- `result` — the normalized contract output returned to the agent.

The effective lookup identity is `(exampleId, toolId, exact contract version, canonicalizer version, canonical arguments)`. The hash is an integrity/index value; readable fields remain in miss diagnostics.

## Canonicalization rules (`1.0.0`)

1. Arguments must satisfy the exact contract input schema before lookup.
2. Serialize as UTF-8 JSON with object keys sorted recursively, no insignificant whitespace, Unicode preserved, and non-finite numbers rejected.
3. Canonicalize representation only. Preserve array order and semantic distinctions including `5` versus `5.0`, case, surrounding whitespace, absent versus explicit `null`, and explicit values versus omitted defaults.
4. Do not trim, case-fold, insert defaults, reorder arrays, or coerce values.
5. Validate fixture results against the exact contract output schema during registry load.

Object-key-order variants therefore share a key. Meaningfully different arguments remain different keys, even when an implementation might treat them similarly.

## Failure behavior

- An ungranted tool or schema-invalid call raises `MockFixtureError` before lookup.
- A fixture with an unbound contract version, stale argument hash, contract-invalid arguments/result, or duplicate row-scoped key fails registry loading.
- A schema-valid call without an exact fixture raises `UnknownMockFixtureError`. Its diagnostic includes the row, readable `toolId@version`, canonicalizer version, canonical arguments, and SHA-256 value.
- Returned results are deep copies so one consumer cannot mutate the checked-in fixture state for later calls.

## Usage

```python
from pathlib import Path

from src.deterministic_mocks import MockRegistry

registry = MockRegistry.from_repo_root(Path.cwd())
result = registry.invoke(
    "tc-0001",
    "weather.get_current_weather",
    {"city": "Oslo", "units": "metric"},
)
```

The caller supplies `exampleId` deliberately because failure injection is a dataset-row property. The registry does not infer a scenario from prompt text or silently switch between success and failure outcomes.
