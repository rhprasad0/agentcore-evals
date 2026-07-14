# Week 5 Runtime IAM and session-isolation receipt

**Observed:** 2026-07-14 · **Region:** `us-east-1` · **Surface:** scratch AgentCore Runtime

This report records bounded green and red observations under the Runtime's actual execution role. The scratch Runtime used the same deployable weather package shape as the project, a short idle timeout, an exact-runtime trust condition, and an execution policy scoped to the selected model plus Runtime log/trace publication. It was separate from the working weather Runtime so tightening and denial probes could not break the Week 4 deployment.

The machine-readable synthetic receipt is [`docs/assets/week-05-runtime-iam-isolation.json`](../assets/week-05-runtime-iam-isolation.json).

## Probe design

The scratch entrypoint returned only stable probe names, `allow` / `deny` / `error`, and bounded AWS error classes. Live identities, resources, request IDs, policy documents, prompts, responses, logs, and traces remained private and temporary.

The policy retained:

- exact selected-profile Bedrock invocation;
- Runtime log-group discovery plus scoped stream creation and writes;
- X-Ray trace publication and sampling reads required by the telemetry client;
- AgentCore-namespaced metric publication.

It omitted the Week 3 scaffold's broad model resources, `bedrock:CountTokens`, configuration-bundle administration, CloudWatch log reads, and log-resource-policy administration.

## Results

| Probe | Exact action | Expected | Observed | Bounded interpretation |
| --- | --- | --- | --- | --- |
| Selected model | `bedrock:InvokeModel` | allow | allow | The tested selected inference profile remained callable from the Runtime role. |
| Adjacent unapproved model | `bedrock:InvokeModel` | deny | `AccessDeniedException` | The tested model outside the approved resource set was unavailable to the Runtime role. |
| Configuration-bundle mutation | `bedrock-agentcore:DeleteConfigurationBundle` | deny | `AccessDeniedException` | The tested administration capability from the Week 3 scaffold baseline was removed. |
| CloudWatch log read | `logs:FilterLogEvents` | deny | `AccessDeniedException` | Runtime telemetry publication did not require the tested log-reading capability. |

The green operational controls also passed:

- a bounded STS call confirmed that the code was executing with Runtime-provided identity without publishing that identity;
- the Strands selected-model path completed;
- the deployed weather adapter produced its exact normalized success envelope from a synthetic provider response, avoiding any live API key or provider payload;
- the operator lane observed 27 Runtime log events and at least five matching X-Ray traces during the bounded window without retaining their content.

## Session-isolation observation

A canary planted in Session A was present on a second Session A invocation. A fresh Session B reported the canary absent. This supports the narrow claim that the tested in-memory context did not cross those two Runtime sessions.

It does **not** prove universal filesystem isolation, durable-memory behavior, correct session-to-user authorization, or every possible cross-session state path. Runtime sessions are not users; the client still owns user-to-session assignment.

## Claim limits

- Every allow or denial is scoped to the named action, synthetic resource shape, principal class, Region, and invocation context.
- One denied adjacent model does not prove that every non-approved model, profile, or API variant is denied.
- One configuration-bundle deletion denial does not prove every configuration-bundle action is denied.
- One `FilterLogEvents` denial is not a complete CloudWatch authorization audit.
- The synthetic weather control validates the deployed adapter's normalized path without claiming a live external-provider success.
- The policy is a tested Week 5 minimum for this scratch path, not a production security certification.

## Public-safety handling

The committed receipt contains no account ID, live ARN, role/session name, Runtime ID, request/trace ID, raw policy, raw log or trace event, prompt, model response, credential, endpoint, or provider payload. The scratch resources and private operational files are teardown-only state, not repository artifacts.
