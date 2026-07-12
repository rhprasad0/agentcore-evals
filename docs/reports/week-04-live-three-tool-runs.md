# Week 4 Live Three-Tool Runs

This receipt records live Week 4 tool-selection and sequencing behavior without committing raw provider traces, Gateway responses, credentials, endpoints, account identifiers, or full model messages.

## Run context

- Date: 2026-07-12
- Runner: `src/agents/weather.py`
- Direct tools: `get_current_weather`, `calculator`
- Gateway tool: exact allowlisted `web-search___WebSearch`
- Weather provider: OpenWeatherMap Current Weather API
- Gateway authentication: IAM/SigV4
- Raw scrubbed traces: temporary local files only; deleted after extraction
- Retry policy: retry infrastructure/transient failures once; preserve model-selection failures without rerunning until green

## Single-tool controls

| Control | Expected tool | Observed call | Result | Verdict |
| --- | --- | --- | --- | --- |
| Calculate 30% of 72 | `calculator` only | `calculator(expression="0.30 * 72", mode="evaluate")` | `21.6` | Pass |
| Current Oslo weather in metric units | `get_current_weather` only | `get_current_weather(city="Oslo", units="metric")` | Structured success envelope | Pass |
| Verify the Nobel Peace Prize ceremony location using current web sources | `web-search___WebSearch` only | `web-search___WebSearch(query="where is the Nobel Peace Prize ceremony held")` | Successful search with citations | Pass |

The weather answer added subjective prose about it being a good day to be outside. That was not a tool-selection failure, but future response-grounding evaluation should distinguish tool-backed facts from model-authored commentary.

## Combined three-tool conversation

Prompt intent:

1. Retrieve Oslo's current metric temperature.
2. Calculate 30% of the exact retrieved temperature.
3. Verify the Nobel Peace Prize ceremony location using current web sources and cite them.

Observed ordered tool calls:

1. `get_current_weather(city="Oslo", units="metric")`
2. `web-search___WebSearch(query="where is the Nobel Peace Prize ceremony held")`
3. `calculator(expression="0.30 * 25.31")`

Observed intermediate-state check:

- Weather returned `temp: 25.31` with a successful structured envelope.
- Calculator received the exact value `25.31`, not a rounded or invented substitute.
- Calculator returned `7.593`.
- Web Search returned success and the final answer cited public sources.

## Verdict

- All three single-tool controls selected only the expected tool.
- The combined conversation used all three registered tools with no extra semantic-search call.
- Retrieval calls completed before the dependent calculator call.
- The calculator argument faithfully preserved the weather tool's exact numeric output.
- No retry was needed.

This satisfies the Week 4 live-conversation success criterion. It does not replace the remaining ambiguity battery, external MCP trust audit, or direct-weather versus Gateway-weather seam comparison.
