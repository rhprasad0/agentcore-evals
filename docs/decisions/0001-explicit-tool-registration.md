# ADR 0001: Explicit tool registration over semantic discovery

- **Status:** Accepted
- **Date:** 2026-07-12
- **Scope:** Agent tool surfaces in this repository

## Context

AgentCore Gateway can advertise tools directly through MCP and can also expose a semantic-search helper that retrieves likely tools from a larger catalog. External MCP servers similarly return a discovered tool list. Both mechanisms make capability discovery easy.

Discovery is not neutral. Tool names, descriptions, and schemas become model-facing prompt inputs. The available candidate set can also change when a Gateway target or external MCP server changes. If that changing set is automatically registered, a tool-selection evaluation no longer has one stable denominator: a wrong selection could come from the model, retrieval, catalog drift, description drift, or an unreviewed new capability.

Week 4 produced concrete examples:

- Gateway advertised the approved Web Search connector and an unapproved semantic-search helper.
- The AWS Documentation MCP server advertised four tools containing imperative chaining, pagination, and query-rewriting language.
- A new Gateway weather target became discoverable but was not automatically added to the fixed three-tool agent.
- Exact-name filtering made the current registered portfolio inspectable and deterministic.

## Decision

**Discovery supplies candidates; checked-in policy grants capability.**

Each agent registers an explicit tool list. MCP and Gateway listings may be inspected, fingerprinted, and filtered, but they do not automatically expand the model-visible tool surface.

For the Week 4 portfolio, registration remains exactly:

1. direct `get_current_weather`;
2. `calculator`;
3. `web-search___WebSearch`.

The Gateway-backed weather tool exists for controlled seam comparison and future shared use. It is not registered alongside direct weather because two model-visible tools with the same capability would introduce an unnecessary routing ambiguity before the evaluation dataset defines how to grade it.

Selection of an approved remote tool fails closed when its exact name is absent or duplicated. Client session lifetime must cover listing, registration, model use, and invocation.

## Consequences

### Benefits

- Tool-selection accuracy has a stable candidate set.
- Capability changes require code review rather than silently entering model context.
- Description/schema drift can be compared against a checked-in manifest in Week 5.
- Ambiguous and failure cases can be reproduced against the same surface.
- Shared Gateway governance remains available without surrendering registration control.

### Costs

- Every approved addition requires code and manifest changes.
- Large portfolios cannot rely on transparent automatic expansion.
- New Gateway or MCP capabilities may exist but remain unavailable until reviewed.
- Operators must distinguish catalog health from an agent's intentionally narrower capability set.

## Revisit when

Reconsider semantic discovery when the approved catalog is too large for practical static registration and all of the following exist:

1. a versioned capability manifest with provenance and description/schema fingerprints;
2. deterministic recording of the retrieved candidate set for every request;
3. separate evaluation of retrieval recall/precision and final model selection;
4. policy enforcement that prevents unapproved retrieved tools from being invoked;
5. drift gates and human approval for changed external tool surfaces;
6. enough labeled rows to measure the two-stage system rather than treating retrieval as invisible plumbing.

Until then, semantic search may assist operator discovery, but it does not grant the agent a capability.

## Evidence

- [`src/agents/weather.py`](../../src/agents/weather.py)
- [`tests/test_weather_agent_runner.py`](../../tests/test_weather_agent_runner.py)
- [`week-04-external-mcp-trust-audit.md`](../reports/week-04-external-mcp-trust-audit.md)
- [`week-04-weather-seam-comparison.md`](../reports/week-04-weather-seam-comparison.md)
