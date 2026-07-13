# Spike 001: Tool Contract Inspector

## Question

**Given** exact-version tool contracts stored as JSON, **when** a human reviews identity, model-visible schemas, operational limits, and normalized failures, **then** can a dependency-free generated GUI make the review faster without becoming another application to maintain?

## Research

| Approach | Strengths | Costs / mismatch | Verdict |
|---|---|---|---|
| [JSON Forms](https://jsonforms.io/docs/readonly) | Mature JSON Schema rendering, read-only mode, React/Angular/Vue renderer sets | Framework binding, renderer package, and UI-schema concepts; optimized for forms and editing | Too heavy and aimed at the wrong task |
| [react-jsonschema-form](https://rjsf-team.github.io/react-jsonschema-form/docs/) | Mature generated forms and AJV validation | Requires React plus validator packages; form-centric rather than inspection-centric | Useful if contracts become editable in-browser, not now |
| [vanilla-jsoneditor](https://github.com/josdejong/svelte-jsoneditor/blob/develop/README-VANILLA.md) | Excellent tree/text/table modes, search, read-only support, schema validation | Makes generic JSON easier to navigate but does not explain toolId, trust, effects, failure modes, or runtime boundaries | Good future Raw JSON enhancement |
| [Stoplight JSON Schema Viewer](https://github.com/stoplightio/json-schema-viewer) | Collapsible nested schema documentation, validation properties, refs | React component and focused on a schema rather than the surrounding tool contract | Better for deeply nested schemas |
| [jsonschema-diagram](https://github.com/Miskler/jsonschema-diagram) | Interactive graph and self-contained HTML output | Graphs add motion and spatial complexity; these schemas are shallow and the important information is operational metadata | Revisit only if `$ref` graphs become hard to follow |
| Repo-native static inspector | Can present contract semantics directly; no runtime dependencies, bundler, CDN, or server | Small amount of custom rendering code to own | **Selected** |

## Prototype

`build.py` reads every `contracts/tools/*/*.json` file and generates the portable `contract-inspector.html` artifact.

The inspector provides:

- Searchable exact-version contract navigation
- Stable `toolId` versus model-visible runtime-name distinction
- Operational envelope: side effects, result trust, latency, and authorization scope
- Normalized failure-mode badges
- Recursive input-schema rendering with required fields, enums, defaults, and constraints
- Separate success and failure output envelopes
- Raw JSON with copy support
- A field guide explaining the contract vocabulary
- Hash-addressable tool and tab selection
- Dense desktop inspection layout

## Run

```bash
python3 spikes/001-contract-inspector/build.py
```

Then open:

```text
spikes/001-contract-inspector/contract-inspector.html
```

The generated file is self-contained and can be opened directly; it does not fetch scripts, styles, fonts, or contract data from the network.

## Verification

- Generator compiled and executed successfully.
- Generated artifact contains all three exact-version contracts.
- JSDOM exercised tool selection, natural-language search, input/output tabs, hash routing, and the field guide with no runtime errors.
- Chromium rendered at 1440×960 with no console errors or document-level horizontal overflow.
- A desktop screenshot is saved beside the artifact.
- Verification caught and fixed one real issue:
  - natural-language `web search` did not initially match `search.web_search`;

### Visual audit

This is a **Command / Inspect** surface: selection and object detail dominate, not a marketing hero or decorative dashboard.

AI-design-slop score: **0/10**. The artifact has no tech gradient, generic indigo, feature-tile grid, accent rails, glass blur, monument stats, icon toppers, centered composition, default Inter typography, or wrong-surface framing.

## Verdict: VALIDATED

### What worked

- A semantic view is substantially easier to scan than prettified raw JSON.
- The overview reveals the contract's operational meaning without hiding exact source values.
- Input and output views preserve schema constraints while removing punctuation noise.
- A generated static artifact fits the repository's zero-runtime-dependency root tooling.
- Raw JSON remains one click away, so the GUI does not become a second source of truth.

### What did not need a library

The current contracts are shallow. A general JSON editor, generated form framework, or schema graph would add installation and maintenance work without improving the most important inspection tasks.

### Constraints

- The HTML must be regenerated after contract changes.
- The renderer supports the schema constructs currently used by this repository; unusual future constructs may need explicit UI treatment.
- This is read-only by design. Editing remains in source JSON so schema validation and review stay authoritative.

## Recommendation for the real build

Promote this approach rather than introducing React:

1. Move the generator into repository tooling, for example `scripts/build_contract_inspector.py`.
2. Generate an ignored local artifact such as `artifacts/tool-contract-inspector.html`.
3. Add one convenience command, such as `make inspect-contracts`, that validates contracts, builds the artifact, and opens it locally.
4. Keep the inspector read-only and source-derived.
5. Add capability-manifest and contract-to-manifest views after the real Week 5 manifest exists.
6. Consider embedding `vanilla-jsoneditor` only if Raw JSON search/tree navigation becomes valuable enough to justify a vendored or pinned browser bundle.
