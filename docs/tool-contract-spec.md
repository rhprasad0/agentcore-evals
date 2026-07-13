# Tool contract specification

**Status:** Week 5 normative contract for the three-tool portfolio

**Applies to:** `agents.weather@3.0.0` and its exact tool grants

**Contract boundary:** final model-visible tool specification plus adapter-normalized result

## Purpose

This specification turns the portfolio's tool conventions into machine-checkable behavior. A tool contract is the reviewed source of truth for what the model may call and what normalized result the agent receives. A capability manifest is the reviewed source of truth for which exact tool contracts an agent may register.

The contract is authored first; runtime tools must conform to it. It is not generated from implementation code after the fact. This direction lets description, schema, side-effect, trust, and failure changes break validation instead of silently changing evaluation behavior.

Current artifacts:

- [`tool-contract.schema.json`](../schemas/tool-contract.schema.json)
- [`capability-manifest.schema.json`](../schemas/capability-manifest.schema.json)
- [`agents.weather@3.0.0`](../contracts/manifests/agents.weather/3.0.0.json)
- [`weather.get_current_weather@2.0.0`](../contracts/tools/weather.get_current_weather/2.0.0.json)
- [`calculator.calculate@2.0.0`](../contracts/tools/calculator.calculate/2.0.0.json)
- [`search.web_search@2.0.0`](../contracts/tools/search.web_search/2.0.0.json)
- [`validate_tool_portfolio`](../src/contracts.py)

## Contract boundary

A contract governs two surfaces:

1. **Final model-visible specification:** exact runtime name, description, and input schema after decorators, wrappers, discovery, and Gateway transformations.
2. **Normalized result:** the success or failure envelope returned to the agent after the seam adapter has handled provider, Lambda, Gateway, or MCP payloads.

The following are outside the contract output boundary:

- raw provider responses;
- Lambda event and response shapes;
- MCP `content`, `status`, and `isError` transport fields;
- Gateway transformation internals;
- model reasoning or causal explanations;
- the correctness of a value merely because its JSON shape validates.

Adapter tests own raw-to-normalized semantics. Contract validation owns the normalized shape. For example, a schema can require `units: "metric"`; it cannot prove that a provider value was converted to Celsius correctly.

A handled domain failure can travel through MCP with transport success. The Week 4 Gateway comparison observed exactly this: the normalized `upstream_4xx` payload survived while MCP reported `status: "success"` and `isError: false`. Evaluators must inspect both axes rather than treating transport success as tool-domain success.

## Exact identity and version binding

Every registered tool resolves to one exact `toolId@version` granted by one exact `manifestId@version`. Version ranges are not accepted.

The current constructor sequence is:

1. load and schema-validate the capability manifest;
2. load the exact contract path for every grant;
3. schema-validate each contract and verify its internal identity matches its path and grant;
4. resolve each candidate by its final model-visible name;
5. reject unknown or duplicate tools;
6. enforce the manifest side-effect ceiling;
7. compare final name, description, and input schema;
8. pass only the validated portfolio to `Agent(...)`.

A description change is behaviorally significant because it can change tool selection. Under the Week 5 policy, any change that can invalidate existing dataset expectations or labels—including a model-visible description change—requires a major contract version. Exact readable versions are the join keys; hashes may supplement integrity later but do not replace versions.

Week 6 dataset manifests and Week 7 run manifests must pin both the capability manifest and tool contracts. A version change creates a different run identity and requires fixture revalidation; it does not trigger automatic migration.

## Enforcement scope

The manifest is an in-process registration control, not a Python sandbox or universal authorization layer.

| Surface | Registration or execution path | Contract/manifest enforcer | Outer control | Negative test or receipt | Known bypass or claim limit |
| --- | --- | --- | --- | --- | --- |
| Direct weather and calculator tools in the Week 5 portfolio | `src/agents/weather.py` → `build_agent` → `Agent(...)` | `validate_tool_portfolio` before construction | Process identity and local/deployed environment | Unmanifested direct tool, duplicate ID, ceiling violation, description/input drift | Code that invokes the implementation directly without this constructor bypasses registration enforcement |
| Gateway-discovered Web Search in the Week 5 portfolio | MCP discovery → exact raw-name selection → contract-owned wrapper → `build_agent` | Exact-name selector plus `validate_tool_portfolio` against the wrapper's final spec | Gateway IAM and MCP session boundary | Missing/duplicate approved discovery result and unmanifested discovered-tool tests | The validator authorizes the wrapper's model-visible capability, not the provenance or honesty of external result text |
| Gateway weather comparison target | Controlled comparison harness invokes the target directly; it is not registered in the portfolio | Seam adapter and contract-focused comparison tests; no portfolio-manifest grant | Gateway execution role and target configuration | Direct-versus-Gateway schema/result comparison | Controlled test surface only; its existence in discovery does not grant it to the agent |
| Week 1 `caller_identity` agent | Module-level `Agent(..., tools=[caller_identity])` | None; constructor is inventoried by the AST test | Developer AWS identity and IAM | Constructor inventory fails if the known set changes | Legacy learning artifact and explicit manifest bypass; no Week 5 enforcement claim |
| Deployed Week 3 weather Runtime | Session-local factory constructs `Agent(..., tools=[get_current_weather])` inside the CodeZip package | None yet; constructor is inventoried by the AST test | Runtime session isolation and execution-role IAM | Constructor inventory plus the bounded Week 3 session probe | Root contract artifacts are outside the deployed package boundary; this is a known bypass, not silently treated as compliant |
| Raw SDK, HTTP, filesystem, or shell access from Python code | Arbitrary application code | None | IAM, Runtime/network configuration, dependency review, and application tests where applicable | No universal negative test exists | A manifest cannot prevent out-of-band calls or malicious code that preserves the same tool interface |
| Gateway Policy, future Week 15 | Calls that transit an associated Gateway | AgentCore Policy | Gateway identity and policy association | Week 15 denial traces | Does not govern direct tools, arbitrary SDK calls, or in-process MCP paths that bypass the associated Gateway |

The constructor-inventory test covers repository-owned source roots. It is not proof that dependencies, generated code, or dynamically imported modules contain no other constructors.

## Side effects and result trust

`sideEffects` and `resultTrust` answer different questions:

- `sideEffects` describes what invoking the tool can change: `none`, `read_external`, or `write_external`.
- `resultTrust` describes how returned content must be treated: `trusted_structured` or `untrusted_external`.

Web Search is `read_external` and `untrusted_external`: it does not mutate an external resource, but fetched text is attacker-shaped input. Weather is `read_external` and `trusted_structured` only after its adapter reduces the provider response to the closed normalized envelope. Calculator is `none` and `trusted_structured`.

The manifest ceiling is a maximum capability level. It does not sanitize untrusted content and does not prove that an implementation lacks hidden side effects.

## Failure envelope

The current v2 contracts use this closed normalized envelope:

```json
{
  "ok": false,
  "error": {
    "kind": "timeout",
    "message": "public-safe diagnostic summary",
    "retryable": true
  }
}
```

`kind` determines the baseline degradation behavior. `retryable` is occurrence-level evidence and may differ within one kind: weather 404 and 429 both normalize to `upstream_4xx`, while only 429 is retryable. `message` is bounded diagnostic text for the agent; it must not contain secrets, credentials, raw provider bodies, account identifiers, request IDs, or stack traces.

The current v2 output schemas allow only `kind`, `message`, and `retryable`. Diagnostic `source` or provider-code fields belong in traces until a versioned contract explicitly adds them. They must not be inserted ad hoc because `additionalProperties: false` intentionally rejects envelope drift.

### Universal degradation assertions

For every normalized failure, the final agent response must:

1. not present fabricated tool data or imply the call succeeded;
2. acknowledge that the requested operation or result is unavailable or invalid;
3. preserve the distinction between a domain failure and transport success;
4. give a next step appropriate to the failure and its `retryable` value;
5. avoid exposing raw diagnostics or credentials.

Deterministic gates can prove the envelope shape, allowed kind, retry flag, absence of forbidden result fields, and absence of known sensitive canaries. A calibrated judge can assess whether the response acknowledges the failure and offers an appropriate next step. Human review remains the arbiter for ambiguous wording and taxonomy changes.

## Six-kind failure taxonomy

| Kind | Normalized condition | Baseline user-facing behavior | Retry qualifier | Bounded diagnostics | Evaluation ownership |
| --- | --- | --- | --- | --- | --- |
| `bad_input` | Required input is absent, malformed, outside the closed enum/range, or unsupported by the capability | Identify the invalid requirement without inventing a result; ask for the smallest correction needed to make a valid call | `false`; do not repeat unchanged input | Name the invalid field or supported boundary, not the full prompt | Deterministic: envelope, no success fields, `retryable=false`. Judge: correction request is specific and useful |
| `auth` | The tool's required credential is missing or rejected | State that the capability is unavailable because its access configuration failed; do not ask the user to paste a secret; direct the operator or user toward configuration rather than another identical call | `false` for the current occurrence; retry only after credentials or authorization change | Public-safe credential surface and rejection class only; never secret values or live identity data | Deterministic: kind, no result data, `retryable=false`, secret-canary absence. Judge: no credential disclosure request and appropriate configuration next step |
| `upstream_4xx` | The external provider rejected a well-formed invocation, including not-found and rate-limit responses | State that the provider could not satisfy the request; do not fabricate the requested external fact; tailor the next step to the occurrence's retry flag when available | Occurrence-level: current weather 404 is `false`; 429 is `true`. The kind alone never authorizes retry | Scrubbed status class or bounded provider code may remain in trace diagnostics; the v2 envelope uses public-safe message text | Deterministic: kind and explicit retry flag; 404/429 fixtures distinguish occurrences. Judge: next step agrees with retryability without overclaiming provider state |
| `upstream_5xx` | Provider/server failure or an invalid/unexpected upstream result shape | Say the upstream capability failed or returned an unusable result; withhold external facts that were not validated; offer a later retry or another grounded path | `true` in current weather and Web Search adapters; Week 12 adds bounded attempts and backoff | Failure class or scrubbed status/shape category; no raw provider body | Deterministic: no success payload, retry flag, no fabricated values. Judge: temporary/unusable framing and grounded alternative |
| `timeout` | The adapter's invocation deadline expires before a normalized result arrives | Say the operation timed out and no result was confirmed; do not infer that the provider completed or failed; offer a bounded retry when policy permits | `true` for current weather occurrences; Week 12 decides attempt count, budget, and idempotency constraints | Declared latency budget and timeout source in traces; no internal stack or endpoint | Deterministic: elapsed-budget fixture, kind, no result. Judge: uncertainty is preserved and retry wording is bounded |
| `network` | Connection, DNS, TLS, or equivalent transport connectivity failure prevents a provider result | Say the service could not be reached and no external result was obtained; offer a bounded retry or later attempt | `true` for current weather occurrences; retry remains constrained by the Week 12 policy | Scrubbed transport class only; no private hostnames, addresses, or headers | Deterministic: injected network exception, kind, no result. Judge: distinguishes unreachable service from provider rejection |

### Current tool coverage and claim limits

- Weather declares all six kinds and has direct unit fixtures for each occurrence class.
- Calculator declares only `bad_input`; its wrapper currently normalizes dependency exceptions and malformed/non-finite results into that kind. This is a bounded calculator contract, not a claim that every internal dependency failure is semantically user input.
- Web Search declares `bad_input` and `upstream_5xx`; Gateway invocation exceptions, transport-error results, malformed JSON, and malformed result shapes currently collapse into `upstream_5xx`. Trace provenance in later weeks must preserve which seam failed even though the agent receives one normalized kind.
- A new kind is justified only when the required user-facing degradation behavior cannot be represented by an existing kind plus `retryable` and bounded diagnostics. Taxonomy changes require a contract version change and downstream fixture review.

## Isolation and authorization layers

The portfolio relies on complementary controls. None substitutes for another.

### Manifest enforcement

The manifest limits tool objects supplied through the enforced constructor. It fails before `Agent(...)` for unknown tools, duplicate IDs, side-effect ceiling violations, exact-version mismatches, or final-spec drift. It does not isolate memory, filesystem, network, or arbitrary Python calls.

### Runtime session isolation

AgentCore Runtime provides the platform session boundary. The Week 3 probe established a narrower observed claim: Session A recalled its inert canary while Session B returned `NO_CONTEXT` in that run. This proves the tested conversation context did not cross those sessions; it does not prove universal filesystem isolation, durable memory behavior, or correct session-to-user authorization.

The application also keeps a bounded in-process Agent cache keyed by Runtime session ID. That cache is best-effort continuity, not durable memory, and resets on cold start or eviction. The client remains responsible for assigning session IDs to users correctly.

### Execution-role IAM

The Runtime role constrains AWS API actions available to deployed code. It does not govern the direct OpenWeather HTTPS request. The Week 3 baseline identified broad model, CloudWatch read/admin, and configuration-bundle grants that Week 5 must test before removing.

A green weather invocation proves only that the tested model/tool path still worked. A red denial proves only the tested action, resource shape, principal class, and session context. Neither result alone proves complete least privilege.

### Gateway controls

Gateway IAM and future AgentCore Policy govern calls that transit the relevant Gateway. They do not cover direct tools, alternate constructors, raw SDK calls, or in-process MCP traffic routed elsewhere. Manifest grants may inform future policy authoring, but compilation is not automatic and residual uncovered paths must remain explicit.

## Public-safe IAM receipt contract

The deployed IAM task records private observations under the actual deployed Runtime execution role, then commits only synthetic summaries with this shape:

| Field | Requirement |
| --- | --- |
| `probeName` | Synthetic stable name for the green or red probe |
| `principalClass` | `deployed Runtime execution role`; never a role/session name or ARN |
| `action` | Exact AWS action tested |
| `resourceShape` | Synthetic resource pattern with placeholders, never a live ARN or identifier |
| `expectedDecision` | `allow` or `deny` |
| `observedDecision` | `allow`, `deny`, or a bounded AWS error class |
| `pairedControl` | Green path or baseline removal that makes the probe meaningful |
| `interpretation` | One sentence stating what the observation supports |
| `claimLimit` | One sentence stating action/resource/principal/context boundaries |

Committed receipts exclude account IDs, ARNs, role and session names, Runtime IDs, request IDs, raw policies, CloudTrail/log events, prompts, arguments, provider responses, endpoints, and credentials.

Required Week 5 probe families are:

- green selected-model, weather-tool, and telemetry paths;
- red unapproved model or profile invocation;
- red configuration-bundle mutation;
- red removed CloudWatch read or administration action.

Each red probe must correspond to a permission removed from the recorded Week 3 baseline. An unrelated easy denial is not evidence that the tightened role preserved the intended boundary.

## Downstream consumers

| Consumer | Contract fields consumed |
| --- | --- |
| Week 6 dataset and mocks | Exact manifest/contract versions, `toolId`, input/output schemas, failure kinds, retry occurrences, result trust |
| Week 7 trace normalization | Exact run identity, normalized result kind, transport/domain distinction, source provenance outside the v2 envelope |
| Week 8 deterministic gates | Tool selection, argument schema, output envelope, latency budget, no-tool declarations, failure assertions |
| Week 9 human labels | Baseline degradation behavior and explicit retry qualifiers |
| Week 11 multi-tool chains | Side effects, untrusted external content, failure propagation |
| Week 12 reliability | Occurrence-level `retryable`, latency budget, bounded attempts, idempotency, credential scope |
| Week 15 policy and screening | Manifest grants as reviewed policy input, side-effect residue, `untrusted_external` screening targets, uncovered direct paths |

## Verification expectations

A Week 5 contract change is complete only when:

- both JSON Schemas and every checked-in instance validate;
- valid and single-defect invalid fixtures behave as expected;
- the enforced portfolio resolves to exact grants before agent construction;
- direct and discovered unmanifested tools, duplicate IDs, ceiling violations, and final-spec drift fail loudly;
- normalized success and failure fixtures satisfy each tool's output schema;
- constructor inventory remains current;
- changed public artifacts pass the repository safety scan and Gitleaks.

## Evidence and sources

- [Week 5 curriculum guide](weeks/week-05-tool-contracts.md)
- [Week 3 local-versus-Runtime report](local-vs-agentcore.md)
- [Week 3 execution-role baseline](execution-role-baseline.md)
- [Week 4 direct-versus-Gateway comparison](reports/week-04-weather-seam-comparison.md)
- [Explicit tool-registration decision](decisions/0001-explicit-tool-registration.md)
- [AgentCore Runtime security best practices](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html)
- [AgentCore Runtime IAM permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
