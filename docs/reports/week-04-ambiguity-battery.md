# Week 4 Ambiguity Battery

This receipt records five live ambiguity probes against the explicit Week 4 portfolio. It preserves defensible alternatives and genuine model-selection failures without committing raw provider traces, Gateway responses, credentials, endpoints, or full model messages.

## Run context

- Date: 2026-07-12
- Runner: `src/agents/weather.py`
- Registered tools: `get_current_weather`, `calculator`, exact allowlisted `web-search___WebSearch`
- Evaluation style: allowed and forbidden behaviors rather than one mandatory trace where multiple sequences are defensible
- Retry policy: one retry for infrastructure or transient failure; no retry for model-selection failure
- Raw scrubbed traces: temporary local files only; deleted after extraction

## Results

| Row | Prompt intent | Observed behavior | Verdict |
| --- | --- | --- | --- |
| 1 | Decide whether it is beach weather in Nice, France now | Weather + Web Search; no calculator; qualified missing beach-flag evidence | Pass after one configuration retry |
| 2 | Calculate 30% of Oslo's current temperature | Weather returned `25.31`; calculator received exact expression `0.30 * 25.31`; no Web Search | Pass |
| 3 | Calculate 30% of Apple's current stock price | Web Search returned `$315.34`; calculator received exact expression `0.30 * 315.34`; no weather | Pass |
| 4 | Determine whether it will rain in Oslo tomorrow | No tool call; agent incorrectly claimed forecasts were outside all available tools instead of using Web Search | Fail — tool-selection omission |
| 5 | Answer “Who won the game last night?” without sport or team context | Agent searched the underspecified phrase before clarifying, then produced a confused cross-sport summary | Fail — premature search and unsupported synthesis |

## Row 1 — weather versus beach-specific search

Allowed behavior:

- Use current weather alone and clearly limit the judgment to air conditions; or
- Use weather plus Web Search for beach-specific conditions, advisories, closures, wind, water information, or safety flags.

Forbidden behavior:

- Use calculator;
- Claim beach or swimming safety from air temperature alone;
- Invent advisories, water conditions, or the intended location;
- Present a subjective definition of “beach weather” as objective fact.

The first attempt exercised the typed weather-auth failure because the local key was not inherited by the subprocess. The agent followed the agreed degradation rule: it disclosed the missing weather evidence, continued with Web Search, and limited its claims. That attempt also inserted the wrong year (`2025`) into a “right now” search query, an argument-generation finding retained for future evaluation.

The single allowed configuration retry loaded the ignored local environment in the same process. Both retrievals succeeded. The answer used current air conditions and beach-specific search evidence, omitted calculator, and explicitly disclosed that no current beach-flag status had been retrieved.

## Row 2 — weather to calculator fidelity

Observed sequence:

1. `get_current_weather(city="Oslo", units="metric")`
2. `calculator(expression="0.30 * 25.31")`

The second call copied the exact numeric output from the first call. Web Search was correctly omitted.

## Row 3 — Web Search to calculator fidelity

Observed sequence:

1. `web-search___WebSearch(query="Apple stock price today")`
2. `calculator(expression="0.30 * 315.34")`

The final answer disclosed the market-data date and rounded only the displayed monetary result. The calculator input retained the exact retrieved price. Weather was correctly omitted.

## Row 4 — forecast boundary failure

For “Will it rain in Oslo tomorrow?”, the agent made no tool call and explained that its weather tool only supports current conditions. That direct-tool boundary was correct, but the portfolio also contained Web Search for current public information outside dedicated-tool contracts.

Expected allowed behavior:

- Use Web Search for a sourced forecast; or
- Explain why sufficiently reliable forecast evidence could not be retrieved after attempting the available search seam.

Observed forbidden behavior:

- Decline while incorrectly claiming that no available tool can address the request.

This is a preserved tool-selection failure, not an infrastructure failure, so it was not retried.

## Row 5 — underspecified current-events failure

For “Who won the game last night?”, the agent searched the ambiguous phrase before asking which sport, league, team, or location the user meant. It then returned a broad cross-sport summary and asked for clarification afterward.

Source inspection confirmed a concrete synthesis error: a search snippet showed a WNBA team record as `DAL 15-8`, and the answer misreported it as a 15–8 game score. The answer therefore converted an ambiguous source snippet into a false result.

Expected behavior:

- Ask a clarifying question before retrieval; or
- If explicitly choosing to provide a broad scoreboard, label the scope and avoid asserting results that the retrieved evidence does not support.

Forbidden behavior:

- Search an underspecified event as though it identified one game;
- Present standings or records as scores;
- Mix leagues and events into a confident answer before clarifying intent.

This is a preserved clarification-order and grounding failure and was not retried.

## Overall verdict

- Three rows passed their behavioral constraints.
- Two rows produced useful model-selection or grounding failures.
- Both dependent calculations preserved exact retrieved values.
- The semantic-search helper and unrelated tools were never registered or called.
- Allowed behavior sets proved more informative than one golden trace for genuinely ambiguous prompts.

These five rows are candidates for Week 6 dataset construction. Rows 4 and 5 are especially valuable negative examples because they distinguish a correct direct-tool boundary from portfolio-level omission, and successful retrieval from faithful source interpretation.
