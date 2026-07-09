# Week 2 Weather Agent Conversations

This note starts the Week 2 conversation log for the Strands weather specimen. It records observed behavior at the agent loop level without committing raw provider traces or secrets.

## Run context

- Script: `src/agents/weather.py`
- Tool: `get_current_weather`
- Tool source: `src/tools/weather.py`
- Live weather provider: OpenWeatherMap Current Weather API
- Secret handling: `OWM_API_KEY` loaded from local `.env`; never print or commit the key.
- Sanitization rule: replace any API key or `appid=` value with `<OWM_API_KEY>` before adding raw snippets.

## Tool schema inspection

Command:

```bash
python src/agents/weather.py --inspect-tool
```

Observed model-facing tool surface:

- Tool name: `get_current_weather`
- Required input: `city`
- Optional input: `units`, default `metric`
- Description includes the core scope boundary: current weather only; not forecasts, history, or climate averages.

Evaluation note: this is the first Week 2 proof that the Python function name, type-hinted signature, and docstring become the model's tool-selection surface. The model does not inspect the implementation; it chooses from the exposed name, description, and JSON schema.

## Conversation probes started

Ryan ran the first three local prompts and reported these outcomes.

### 1. Current weather — should call tool

Prompt family:

```text
What's the current weather in Seattle?
```

Observed behavior:

- Agent called the weather tool.
- Tool returned current weather from OpenWeatherMap after the API key became active.
- This is the expected behavior for a current-weather request with a named city.

Evaluation note:

- **Tool-selection behavior:** pass — the request matched the tool description and required schema.
- **Response-boundary behavior:** pending raw trace review — final answer should report the tool result without inventing extra forecast/history details.

### 2. Forecast request — should not call current-weather tool

Prompt family:

```text
Will it rain in Paris tomorrow?
```

Observed behavior:

- Agent rejected the forecast request rather than using the current-weather tool.
- This matched the docstring boundary: the tool is not for forecasts.

Evaluation note:

- **Tool-selection behavior:** pass — no current-weather call for a forecast request.
- **Response-boundary behavior:** likely pass if the final answer clearly explains the limitation instead of fabricating a forecast.

### 3. Math request — should not call weather tool

Prompt family:

```text
What's 2+2?
```

Observed behavior:

- Agent answered the math question directly.
- It did not need the weather tool.

Evaluation note:

- **Tool-selection behavior:** pass — no irrelevant weather tool call.
- **Response-boundary behavior:** intentionally undecided for Week 2. The current criterion is tool-selection correctness, not whether this agent should refuse every non-weather request.

## Early takeaways

- The scoped docstring appears to matter: the model distinguished current weather from forecast requests.
- Non-weather prompts can still be answered directly; that is not a tool-selection failure unless the weather tool is called.
- These three probes become future dataset rows: one `should_call` row and two `should_not_call` rows.

## Failure probes

These runs used a temporary local probe script to summarize `agent.messages` without committing raw provider traces. The script was removed after the run.

### 4. Missing API key — should call tool, then explain `auth`

Prompt:

```text
What's the current weather in Seattle?
```

Setup:

- Temporarily removed `OWM_API_KEY` from the process environment.

Observed tool call:

```json
{
  "name": "get_current_weather",
  "input": {
    "city": "Seattle"
  }
}
```

Observed tool result:

```json
{
  "ok": false,
  "error": {
    "kind": "auth",
    "message": "OWM_API_KEY is not set",
    "retryable": false
  }
}
```

Observed final-answer behavior:

- Agent explained that the weather service had an authentication/configuration issue.
- Agent stated the failure was not retryable.
- Agent did not invent a Seattle temperature or conditions.

Evaluation note:

- **Tool-selection behavior:** pass — a current-weather request still needed the tool.
- **Failure-handling behavior:** pass for Week 2 observation — the model used the envelope instead of fabricating weather.

### 5. Invalid city — should call tool, then explain `upstream_4xx`

Prompt:

```text
What's the current weather in NotARealCityNameForAgentCoreFailureProbe?
```

Observed tool call:

```json
{
  "name": "get_current_weather",
  "input": {
    "city": "NotARealCityNameForAgentCoreFailureProbe"
  }
}
```

Observed tool result:

```json
{
  "ok": false,
  "error": {
    "kind": "upstream_4xx",
    "message": "weather API returned status 404",
    "retryable": false
  }
}
```

Observed final-answer behavior:

- Agent explained that the weather API could not locate the city.
- Agent correctly treated the same request as non-retryable.
- Agent did not invent weather for the fake city.

Evaluation note:

- **Tool-selection behavior:** pass — the prompt was still a current-weather request.
- **Failure-handling behavior:** pass for Week 2 observation — the model mapped the structured 4xx envelope into an honest user-facing answer.

### 6. Empty city request — model refused before tool call

Prompt:

```text
Get the current weather for an empty city name: ''.
```

Observed behavior:

- Agent did not call the weather tool.
- Agent asked for a valid named city.

Evaluation note:

- **Tool-selection behavior:** acceptable but interesting — the model enforced the required `city` input before tool execution, so this did not exercise the tool's `bad_input` envelope.
- **Dataset-design note:** if Week 6 needs a deterministic `bad_input` row, use a mocked/direct tool execution path or a prompt that reliably causes an empty argument. Do not assume the model will pass invalid arguments just because the user asks it to.

## Boundary and argument-mapping probes

These runs used a temporary local probe script to summarize `agent.messages`; the script was removed after the run.

### 7. Fahrenheit request — should map to `units="imperial"`

Prompt:

```text
What's the weather in Oslo in Fahrenheit?
```

Observed tool call:

```json
{
  "name": "get_current_weather",
  "input": {
    "city": "Oslo",
    "units": "imperial"
  }
}
```

Observed tool result:

```json
{
  "ok": true,
  "city": "Oslo",
  "temp": 78.55,
  "units": "imperial",
  "conditions": "broken clouds"
}
```

Observed final-answer behavior:

- Agent reported the temperature in Fahrenheit.
- Agent preserved the current-weather scope.

Evaluation note:

- **Argument-mapping behavior:** pass — the model mapped the user's Fahrenheit phrasing to the tool's `units="imperial"` argument.
- **Dataset-design note:** this becomes a useful future row because it checks argument extraction, not just call/no-call selection.

### 8. Historical-weather request — should not call current-weather tool

Prompt:

```text
What was the weather in Seattle yesterday?
```

Observed behavior:

- Agent did not call the weather tool.
- Agent explained that it can provide current weather only, not historical weather.

Evaluation note:

- **Tool-selection behavior:** pass — no current-weather call for a historical-weather request.
- **Response-boundary behavior:** pass for Week 2 observation — the model used the “not history” tool-description boundary rather than answering from memory or fabricating yesterday's weather.

## Docstring A/B probe

This probe temporarily changed the weather tool docstring from the scoped description:

```text
Get current weather for a city. Not forecasts, history, or climate averages.
```

to the broad description:

```text
Get weather for a city.
```

The probe used a neutral system prompt so the tool docstring had more influence than the agent runner's normal weather-only boundary prompt. The broad docstring was restored to the scoped version after the run.

### 9. Forecast prompt under broad docstring

Prompt:

```text
Will it rain in Paris tomorrow?
```

Observed behavior with broad docstring:

- Agent called `get_current_weather` with `city="Paris"`.
- Agent returned current Paris conditions, then caveated that it could not provide tomorrow's forecast.

Observed behavior with scoped docstring under the same neutral system prompt:

- Agent still called `get_current_weather` with `city="Paris"`.
- Agent again returned current Paris conditions, then caveated that forecasts are unavailable.

Evaluation note:

- **A/B result:** inconclusive/negative for the expected docstring-only effect. For this model and neutral prompt, the scoped docstring alone did not stop a forecast-adjacent current-weather lookup.
- **Important distinction:** the normal `src/agents/weather.py` system prompt did reject the forecast request earlier. That means the effective boundary currently comes from the combination of system prompt plus tool description, not the docstring alone.
- **Future eval row:** forecast prompts should check both tool selection and final-answer caveat. A model may call current weather for context but still avoid claiming a forecast.

### 10. Historical prompt under broad docstring

Prompt:

```text
What was the weather in Seattle yesterday?
```

Observed behavior with broad docstring:

- Agent did not call the weather tool.
- Agent explained that historical weather is unavailable.

Observed behavior with scoped docstring under the same neutral system prompt:

- Agent again did not call the weather tool.
- Agent explained that it only supports current weather.

Evaluation note:

- **Tool-selection behavior:** pass in both variants.
- **A/B result:** no meaningful difference for the history prompt.
- **Design lesson:** do not overclaim that a docstring boundary alone enforces scope. Treat docstrings as one behavior-shaping surface, then verify with traces.

## Deterministic tool-level coverage

Some failures are better proven at the tool boundary than by trying to trick the model into malformed calls or real network outages. The offline unit tests cover every `FAILURE_KINDS` value without network or a real API key:

- `bad_input` — empty city and invalid units.
- `auth` — missing key and 401/403 responses.
- `upstream_4xx` — 404 and retryable 429.
- `upstream_5xx` — 5xx status and malformed upstream payload.
- `timeout` — `requests.Timeout`.
- `network` — `requests.RequestException` such as connection failure.

Evaluation note: Week 2's agent prompts show how the model reacts to envelopes it naturally encounters; the unit tests prove the tool can produce the full closed failure set. Later weeks can combine these with deterministic mocks to force specific agent-level traces.

## Mocked retryable-failure probes

These runs tested the agent's reaction to controlled tool failures without waiting for real outages. A temporary probe script replaced the weather API fetch function at runtime so the Strands-visible tool still ran, but instead of calling OpenWeatherMap it returned a specific failure envelope such as `timeout`, `network`, or `upstream_5xx`.

That let the real model see the same structured tool result it would see in production, while keeping the failure deterministic and safe. In plain English: we did not test OpenWeatherMap here; we tested whether the agent would read a retryable failure object, explain it honestly, and avoid inventing Seattle weather. The temporary probe script was removed after the run.

Shared prompt:

```text
What's the current weather in Seattle?
```

### 11. Timeout envelope

Forced tool result:

```json
{
  "ok": false,
  "error": {
    "kind": "timeout",
    "message": "upstream exceeded 5s",
    "retryable": true
  }
}
```

Observed behavior:

- Agent called `get_current_weather` for Seattle.
- Agent explained that the weather service timed out.
- Agent recognized the error as retryable and suggested trying again.
- Agent did not invent Seattle weather.

### 12. Network envelope

Forced tool result:

```json
{
  "ok": false,
  "error": {
    "kind": "network",
    "message": "ConnectionError",
    "retryable": true
  }
}
```

Observed behavior:

- Agent called `get_current_weather` for Seattle.
- Agent explained that a network connection error blocked retrieval.
- Agent treated the issue as retryable/transient.
- Agent did not invent Seattle weather.

### 13. Upstream 5xx envelope

Forced tool result:

```json
{
  "ok": false,
  "error": {
    "kind": "upstream_5xx",
    "message": "weather API returned status 503",
    "retryable": true
  }
}
```

Observed behavior:

- Agent called `get_current_weather` for Seattle.
- Agent explained that the upstream weather API returned a 503/service-unavailable style failure.
- Agent treated the failure as retryable.
- Agent did not invent Seattle weather.

Evaluation note: the model consistently used `retryable=true` as a user-facing distinction. It did not actually retry, which is correct for Week 2: retry policy belongs in a later deterministic resilience layer, not in ad hoc model behavior.

## Next probes to add

- Decide whether to keep forecast prompts as strict no-call rows or as softer rows that permit current-weather context only if the final answer clearly refuses to forecast.
- Commit the Week 2 conversation checkpoint after reviewing the doc for public-safety and scope.
