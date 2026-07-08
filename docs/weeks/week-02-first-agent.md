# Week 2 — Basic Agent Development with Strands

**Phase:** Foundations (Weeks 1–4) · **Specimen:** the weather agent — the star of Weeks 5–10
**Lanes touched:** agent build lane, entirely local (deliberately cloud-light — see [Appendix A](../../LEARNING_PLAN.md#appendix-a--week--capability-map))
**Prerequisites:** Week 1 exit gate closed — working venv, Bedrock model access, budget alarm.

[← Week 1](week-01-fundamentals.md) · [Week index](README.md) · [Next: Week 3 →](week-03-runtime-deployment.md)

---

## Objective

Build the first real Strands agent with a single tool, understand the agent loop deeply, run it locally, and explore model providers.

## Why this week exists

The weather agent becomes the specimen for the entire eval contract (Weeks 5–10). Building it with explicit error handling now — rather than retrofitting — is what makes its behavior *labelable* later. A tool that fails vaguely cannot be evaluated crisply.

Unpack that last sentence, because it is the week's thesis. In Week 9 a human (you, blind) will look at a trace and assign a label like `errorRecovery: compliant`. That label is only possible if the trace can *distinguish* failure situations: a timeout is not a bad city name is not a revoked API key. If the tool raises raw exceptions, the model sees an arbitrary traceback (or nothing), behaves differently run to run, and the labeler has nothing stable to judge against. If the tool returns a **typed failure envelope** — a closed set of failure kinds, an explicit retryable flag — then "what should the agent do when the tool times out?" becomes a question with a written answer (Week 5's taxonomy), a synthetic test row (Week 6's failure injection), a deterministic gate (Week 8), and a human label (Week 9). One design decision this week powers four weeks of evaluation machinery.

## Concepts

### The specimen mindset

This plan's core inherited lesson: **the specimen stays simpler than the evaluation machinery around it.** The weather agent is deliberately boring — one tool, one API, unambiguous scope — because every ounce of specimen complexity multiplies the ambiguity of every label and gate downstream. You are not building an impressive weather agent this week. You are building a *legible* one: every behavior it can exhibit should be nameable, reproducible, and worth writing down. Resist every "while I'm here" feature. Tool count is a cost ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)).

### Typed failure envelopes — errors as data, not exceptions

At the tool boundary, this repo's tools never let exceptions escape to the agent loop. Instead every tool returns one of two shapes:

- **Success:** `{ok: true, ...payload}`
- **Failure:** `{ok: false, error: {kind, message, retryable}}` where `kind` comes from a **closed set** and `retryable` is explicit.

Why this beats exceptions at this boundary:

1. **The model can act on it.** A structured failure is context the model can reason over ("the tool says retryable timeout") instead of a stack trace it pattern-matches on. What the model *does* with that context is precisely the behavior Weeks 5–9 will specify, inject, gate, and label.
2. **The set is closed.** `FAILURE_KINDS = ("bad_input", "auth", "upstream_4xx", "upstream_5xx", "timeout", "network")` is an enum, not a convention. A closed set is what makes coverage checkable: Week 6's validator can demand every kind has dataset rows; Week 8's harness can gate per-kind; a new failure mode forces a deliberate schema change instead of silently widening behavior.
3. **`retryable` is a policy input, not an adjective.** Week 12's retry layer will read this flag mechanically: retryable kinds get exponential backoff within a budget; non-retryable kinds fail fast to a degradation message. Writing it down now as data means the Week 12 policy needs no tool rewrites.
4. **Determinism becomes possible.** Mocked tools (Week 6) can script exact failures per row. You cannot script "raise something like what requests raises" nearly as crisply as `{ok: false, error: {kind: "timeout", ...}}`.

The distinction to keep sharp: exceptions are still fine *inside* the tool (that's normal Python); the envelope is the *boundary contract* — what crosses from tool to agent loop.

### What the agent does with failure is the actual product

Once failures are data, a new question surfaces, and it is the interesting one: **given `{ok: false, kind: timeout, retryable: true}`, what should the agent say and do?** Retry? How many times? Tell the user what, exactly — "try again later," or "the weather service timed out, here's what I know instead"? Silently answer from the model's own memory of Seattle weather (the worst case: fabrication wearing a helpful face)?

This week you only *observe* what the agent does — run the failure cases and log honestly. Week 5 turns your observations into required behaviors per kind; disagreements between observed and required become your first real eval findings. Do not tune the agent to behave well this week; you'd be tuning against a spec that doesn't exist yet.

### Tool descriptions are prompts

Confirmed in the SDK source: the `@tool` decorator builds the tool spec from your function — **name** from the function name, **description** from the docstring (minus the Args section), **inputSchema** as JSON Schema derived from your type-hinted signature. There is no separate registration file; *the docstring is the interface*. Consequences:

- Editing a docstring is a behavior change to the agent, exactly like editing the system prompt. It gets reviewed, versioned, and (from Week 8 on) regression-gated like one. Week 13's seeded regression is literally a docstring "improvement."
- The docstring's job is *scoping*, not marketing. "Get current weather for a city" invites calls for forecasts and history; a description that states what the tool does **not** do gives the model a reason to decline. You'll formalize this in Week 5 (`description: "Current weather for a city. Not forecasts, not history."`).
- The generated schema is worth inspecting, not assuming — defaults, optionality, and enum-ness of `units` all surface to the model exactly as the decorator derived them, which may not be what you meant.

### Model providers as a controlled variable

The same `Agent` runs against Bedrock (default), the Anthropic API, Ollama locally, or others — but **tool-calling behavior is not portable**: providers differ in eagerness to call tools, willingness to emit parallel calls, argument formatting, and how they behave when no tool fits. For an eval repo this means provider (and model ID, and temperature) is a *pinned variable in every run manifest* (Week 7), because a metric measured under one provider says nothing about another. This week's provider swap is your first taste of that non-portability — collected as notes, not yet as gates.

### Offline testability is an eval requirement, not a nicety

The success criterion "tool unit tests pass offline — no network, no API key" is not general software hygiene sneaking in. Weeks 8 and 13 run this tool's behavior in CI on every PR, deterministically, for free. That only works if the HTTP layer is mockable at a clean seam — which is also the seam Week 6's deterministic mock registry will occupy. If your tests can't fake `requests` responses (success bodies, 4xx/5xx statuses, raised timeouts), fix the tool's structure now while it's forty lines.

## Build steps

### 1. Implement the weather tool with a typed failure envelope

Against OpenWeatherMap (free tier), instead of raw exceptions:

```python
# src/tools/weather.py
import os, requests
from strands import tool

FAILURE_KINDS = ("bad_input", "auth", "upstream_4xx", "upstream_5xx", "timeout", "network")

@tool
def get_current_weather(city: str, units: str = "metric") -> dict:
    """Get current weather for a city. units: 'metric' or 'imperial'.

    Returns {ok, city, temp, conditions} on success or
    {ok: False, error: {kind, message, retryable}} on failure.
    """
    if not city or not city.strip():
        return _fail("bad_input", "city must be non-empty", retryable=False)
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "units": units, "appid": os.environ["OWM_API_KEY"]},
            timeout=5,
        )
    except requests.Timeout:
        return _fail("timeout", "upstream exceeded 5s", retryable=True)
    except requests.RequestException as exc:
        return _fail("network", str(exc), retryable=True)
    if resp.status_code >= 500:
        return _fail("upstream_5xx", f"status {resp.status_code}", retryable=True)
    if resp.status_code >= 400:
        return _fail("upstream_4xx", f"status {resp.status_code}", retryable=False)
    data = resp.json()
    return {"ok": True, "city": city, "temp": data["main"]["temp"],
            "conditions": data["weather"][0]["description"]}
```

The failure envelope (`kind` ∈ a closed set, `retryable` explicit) is the seed of Week 5's failure taxonomy and Week 6's validators.

Two things about this sketch are deliberately yours to finish, and the exercises below walk you into both: `_fail` is referenced but not defined, and the sketch as written **cannot actually produce every kind in `FAILURE_KINDS`** — auditing it against its own enum is Exercise 1, and the success criteria hold you to the fix.

### 2. Exercise the agent loop deliberately

Three prompt families, run and logged honestly:

- **Should call:** "What's the weather in Seattle?", "Is it raining in Tokyo?", "Weather in Oslo in Fahrenheit?" (does `units` get set?).
- **Should NOT call:** "What's the capital of France?", "What's 2+2?", "What does OWM stand for?" — the agent answering directly (or declining) is *correct*; a tool call here is your first observed misfire.
- **Should fail cleanly:** "Weather in ''?", key unset, network blocked (pull the cable — set an invalid proxy or block the domain). Watch what the model does with each envelope.

Log full conversations to `docs/reports/week-02-conversations.md` — **scrubbed** (no API keys in echoed params, no account identifiers; billboard rule applies to logs especially, since they contain model output you didn't author).

### 3. Swap model providers behind the same agent

Bedrock default vs one alternative (`strands.models` providers: Bedrock, Anthropic, OpenAI via LiteLLM, Ollama, etc.). If you don't hold a second paid API key, Ollama with a local tool-capable model is the free path. Re-run a subset of step 2's battery and note tool-calling behavior differences — eagerness, argument formatting, parallel calls, refusal style. Provider choice is a variable your evals will control for later.

### 4. Write a second custom `@tool` from scratch

Any small utility — purely to internalize the decorator contract: docstring → tool description, signature → input schema. Inspect what the decorator generated rather than assuming. Tool descriptions are prompts; treat them as versioned artifacts from day one.

## Exercises — guided discovery

**1. Audit the sketch against its own enum.** For each of the six `FAILURE_KINDS`, trace the code path that returns it. Which kinds are unreachable as written? What *input state* should produce them, and what does the sketch actually do in that state?
- *Hint 1:* Follow `os.environ["OWM_API_KEY"]` — what happens when that key isn't set? Is the result an envelope?
- *Hint 2:* OWM returns 401 for a bad/missing key. Which kind does the sketch map 401 to — and is that the kind the enum reserves for it?
- *Hint 3:* The success criteria require every kind reachable *in a test* with a *distinct agent response*. Your fix list is exactly the gap between the enum and the reachable set.

**2. Write `_fail` once, use it everywhere.** Define the helper the sketch assumes. What invariants should it enforce so that *no* failure envelope can ever be malformed?
- *Hint 1:* What stops a typo like `kind="timout"` from shipping? Where's the one place to check membership in `FAILURE_KINDS`?
- *Hint 2:* Week 6 will schema-validate these envelopes; anything the helper guarantees now is a validator you half-wrote early.

**3. Find the mocking seam.** Make the tool's unit tests pass with the network cable conceptually cut: every kind, both envelope shapes, no real key.
- *Hint 1:* What's the narrowest thing you can fake — the function, the `requests` module, the transport?
- *Hint 2:* `monkeypatch`/`responses`/`requests-mock` all work; the question is which seam Week 6's mock registry will want to reuse. A mock that substitutes *the whole tool* serves the agent-level harness; a mock at the HTTP layer serves the tool's own tests. You'll eventually want both — where does each live?

**4. Watch the model meet a failure.** With the key unset (after your Exercise 1 fix makes that an `auth` envelope), ask for Seattle's weather. Read the final response letter by letter: does the agent admit failure, invent a temperature, or promise to retry? Then check `agent.messages`: did it re-call the tool?
- *Hint 1:* You're not judging right/wrong yet — there's no spec until Week 5. You're collecting the behaviors that spec must rule on.
- *Hint 2:* Run it three times. Is the behavior even stable? That instability is why Week 8's gates run on mocked determinism and why judges get repeat-run variance checks in Week 10.

**5. Description A/B.** Write two docstrings for the same weather function — one sentence ("Get weather for a city") vs. scoped ("Current weather for a city. Not forecasts, not history."). Run "Will it rain in Paris tomorrow?" under each. Diff the behavior.
- *Hint 1:* Tomorrow is a forecast. Which description gives the model grounds to decline or caveat?
- *Hint 2:* Whatever difference you observe is Week 13's regression mechanism in embryo — a description edit changing selection behavior. Save both docstrings; they're future dataset material.

**6. Schema archaeology.** For your second custom tool, retrieve the generated tool spec and compare it to the schema you *would* have written by hand.
- *Hint 1:* The decorator's `extract_metadata` produces name/description/inputSchema — where does the result surface on the agent or the decorated function?
- *Hint 2:* Check how your default parameter and your `Optional` hints came through. Any surprise here is a contract-drift bug you caught before Week 5 froze the contract.

## Gotchas & drift watch

- **The sketch is a sketch.** Its gaps (missing `_fail`, unreachable kinds, key handling) are teaching material, not oversights to silently patch around — work Exercise 1 before trusting it.
- **OWM realities:** free tier is rate-limited (429s are real — which kind is a 429? Decide and be consistent); city names are ambiguous ("Springfield", "Paris, TX") — note ambiguity cases as future dataset rows rather than solving them now; `units` takes `metric`/`imperial`/`standard`, and the model must *choose* one when the user says "Fahrenheit."
- **`requests` timeout subtlety:** `timeout=5` covers connect and read separately, not total wall time; `requests.Timeout` is the parent of both variants. Good enough here — but note it, because Week 5's `latencyBudgetMs` contract field implies *total* budget and Week 12 will care about the difference.
- **Scrub before committing logs.** The conversation log includes tool results and model text. The API key rides in the request params — make sure your logging never echoes the URL with `appid` in it.
- **Provider-swap cost:** a second hosted provider means a second API key (never committed; env var only). Ollama is the zero-key option; note that small local models may tool-call *much* worse — that observation is itself the point of step 3.
- **Import names:** the pip packages are `strands-agents` and `strands-agents-tools`; imports are `strands` and `strands_tools`. (Verified against current docs 2026-07-07.)
- **Don't gate yet.** The temptation after Exercise 4 is to add retries or prompt rules. Resist — Week 5 writes the spec, Week 8 builds the gates, Week 12 builds the resilience. This week only observes.

## Deliverable checklist — First Functional Agent + Tool

- [ ] Weather agent with typed failure envelope, graceful degradation messages, and unit-tested tool code (mock the HTTP layer).
- [ ] Conversation logs: success, refusal-to-call, and each failure kind, committed scrubbed.
- [ ] Custom `@tool` implementation with notes on how docstring/signature surface to the model.
- [ ] Provider-swap notes (Bedrock vs one other) on tool-calling differences.

## Success criteria

- [ ] Every `FAILURE_KINDS` value is reachable in a test and produces a distinct, user-appropriate agent response.
- [ ] The agent does *not* call the weather tool for non-weather questions (spot-checked now; gated in Week 8).
- [ ] Tool unit tests pass offline — no network, no API key.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07, except where marked external.

- [Strands agent loop concepts](https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/) — the reasoning → selection → execution → feedback cycle; read before step 2 so you know what to watch for in `agent.messages`.
- [Strands `@tool` decorator API reference](https://strandsagents.com/docs/api/python/strands.tools.decorator/) — `extract_metadata` is where docstring → description and signature → inputSchema actually happen; ground truth for Exercise 6.
- [Strands Amazon Bedrock model provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/) — configuration, region, credentials for the default provider.
- [Strands custom model providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/) — the provider abstraction (`stream`/`update_config`/`get_config`); skim to understand what "swappable behind the same Agent" means mechanically.
- [OpenWeatherMap current weather API](https://openweathermap.org/current) *(external)* — parameters, status codes, and error bodies; the source for which HTTP statuses map to which failure kinds.

## Self-check

1. State the two envelope shapes from memory, and name what enforces that `kind` can't be a typo.
2. Why does `retryable` live in the tool's return value rather than in the agent's prompt or the retry code?
3. Your tool raised an exception through to the agent loop in production. Name two downstream eval artifacts (from Weeks 5–9) that failure just made ambiguous.
4. What exactly does the model see about your tool — list the three fields and where each comes from in your source.
5. Why must this week *not* fix the agent's bad failure behavior, only record it?
6. Which observations from this week become dataset rows in Week 6? (There are at least three families.)
