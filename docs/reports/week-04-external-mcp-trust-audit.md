# Week 4 External MCP Trust Audit

This receipt inspects an MCP server the project does not author. It records the advertised tool-selection surface without registering those tools with the Week 4 agent or invoking any documentation operation.

## Audited server

- Package command: `uvx awslabs.aws-documentation-mcp-server@latest`
- Resolved server name: `awslabs.aws-documentation-mcp-server`
- Resolved version: `1.28.1`
- Negotiated MCP protocol version: `2025-11-25`
- Transport: stdio
- Advertised tools: four
- Canonical surface fingerprint (SHA-256): `bb5d63ffa16abb7120e771ed6a425997c72acb6da21cd06a9936716b97f22138`

The fingerprint covers the resolved server metadata, protocol version, and each tool's exact name, description, and input schema. It is an observation, not an enforced pin.

## Advertised surface

| Tool | Description size | Capability |
| --- | ---: | --- |
| `read_documentation` | 1,478 characters | Read and convert an AWS documentation page |
| `read_sections` | 2,049 characters | Extract named sections from a documentation page |
| `search_documentation` | 3,216 characters | Search official AWS documentation |
| `recommend` | 1,725 characters | Retrieve related documentation recommendations |

All four descriptions contain operational guidance in addition to capability statements. None contained an overtly malicious instruction such as “always prefer this tool,” but the surface is still prompt-bearing and selection-steering.

## Prompt-like language

### 1. Cross-tool chaining

The `search_documentation` description tells the model to pass recommended section titles directly to `read_sections`. This does more than explain search output: it proposes the next tool call and therefore shapes orchestration.

Trust implication: a future server author could strengthen that suggestion into mandatory or over-broad chaining, increasing calls and context consumption without any client-code change.

### 2. Repeated-call instructions

The `read_documentation` description instructs the model to make another call with a new `start_index` when content is truncated. This is operationally useful, but it is still a server-authored loop instruction entering the agent's context.

Trust implication: repeated-call guidance can influence cost, latency, and stopping behavior. A client should not assume every pagination instruction is automatically appropriate for its own budget or task.

### 3. Imperative parameter policy

The `search_documentation.search_intent` input description contains an uppercase `CRITICAL` instruction not to include PII or customer data and tells the model how to rewrite user intent.

Trust implication: this particular instruction is protective, but it proves that arbitrary imperative text inside an input schema reaches the same model-facing decision surface as ordinary parameter documentation.

### 4. Discovery expansion

The `recommend` description instructs the model to call the tool after reading a page, to discover popular pages, and to inspect “New” recommendations for recently released information.

Trust implication: a recommendation tool can expand a bounded documentation lookup into an exploratory chain. That may be useful for research but undesirable for a latency- or cost-bounded agent.

## Current drift gap

The command uses `@latest`, so a future launch may resolve a newer package with changed names, descriptions, or schemas. The current setup has no automatic comparison against the recorded fingerprint and would not stop an agent from receiving changed server-authored instructions if these tools were registered directly.

Current defenses:

1. Inspect before registration.
2. Keep the Week 4 agent's tool list explicit; discovery never expands it.
3. Do not register this external server in the production portfolio merely because it is available.
4. Preserve the resolved version and surface fingerprint as an audit receipt.

Week 5 should convert this observation into enforcement:

- pin an exact package/server version where possible;
- manifest exact approved tool names;
- fingerprint descriptions and schemas;
- fail startup or require review when the advertised surface changes;
- keep client-side call, latency, and pagination budgets authoritative over server-authored workflow suggestions.

## Verdict

The AWS Documentation MCP server's descriptions are detailed and generally aligned with its capabilities, but they are not inert metadata. They contain selection, chaining, pagination, query-rewriting, and discovery instructions authored outside this project. The trust boundary is therefore the full advertised MCP tool specification—not merely the executable server process or tool name.
