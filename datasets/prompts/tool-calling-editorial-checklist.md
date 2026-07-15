# Tool-calling corpus editorial checklist

Apply this checklist manually to every row before changing `provenance.reviewStatus` to `reviewed`. Review prompts without looking at `expected` first.

## Blind verdict

- [ ] I can predict the intended tool choice and call count from the prompt alone.
- [ ] The prompt has one intended verdict, or its ambiguity is explicitly the behavior under test.
- [ ] The expected tools are capabilities the exact manifest grants.
- [ ] `mustNotCall` closes plausible over-calling paths.

## Argument fidelity

- [ ] Every constraint names its exact `toolId`.
- [ ] Every constrained path exists in that exact contract's input schema.
- [ ] The predicate is one of the five approved v1 predicates.
- [ ] Allowed values are justified by the prompt rather than evaluator preference.
- [ ] Repeated calls use `coversExactlyOnce` when completeness and duplicate rejection matter.

## Response and failure behavior

- [ ] Every `responseMust` or `responseMustNot` item is observable and falsifiable.
- [ ] The row does not pretend coarse response checks measure overall response quality.
- [ ] Failure behavior matches the frozen Week 5 taxonomy.
- [ ] `retryable` describes the scripted occurrence, not the failure kind in general.
- [ ] Failure rows forbid fabricated data, raw diagnostics, and credential disclosure.

## Family quality

- [ ] Straightforward rows are intentionally boring and decisive.
- [ ] Multi-call rows cannot be satisfied by one clever call.
- [ ] No-tool rows are near the tool boundary and do not leak a trivial length/topic shortcut.
- [ ] Adversarial rows use only the fixed inert canary and make no security claim beyond tested non-propagation.
- [ ] Dependency rows stay within weather → calculator and stop after invalid upstream data.
- [ ] The row is not a cosmetic duplicate of another row.

## Public safety and provenance

- [ ] The row contains no account IDs, ARNs, credentials, private endpoints, emails, raw traces, or realistic secrets.
- [ ] Examples use public places, public sources, and inert synthetic diagnostics.
- [ ] `authoringMethod` accurately records how the row was drafted.
- [ ] `reviewStatus` remains `pending` until this checklist has actually been applied.

## Dataset freeze

Only after all 100 rows pass manual review:

1. change every row's `reviewStatus` to `reviewed`;
2. change the dataset manifest's `reviewStatus` to `human-reviewed`;
3. regenerate validator receipts without silently changing prompts or expectations;
4. treat subsequent row edits as dataset-versioned errata.
