# AgentCore Runtime execution-role baseline

Captured 2026-07-11 in `us-east-1`. This is the Week 3 "before" picture for the generated weather-agent Runtime role. It records what the AgentCore CLI/CDK scaffold granted before Week 5 attempts least privilege.

No IAM policy was changed during this inspection.

## Role shape

The deployed Runtime was `READY` and used:

- one generated execution role
- one inline policy
- no attached managed policies
- no permissions boundary

The trust policy allowed `bedrock-agentcore.amazonaws.com` to call `sts:AssumeRole`.

The trust relationship did not include `aws:SourceAccount` or `aws:SourceArn` conditions. AWS recommends both to reduce confused-deputy risk, with the full Runtime ARN preferred when known. That is a Week 5 hardening candidate, not a Week 3 edit.

## Granted permissions

### Bedrock model access

The role allowed:

- `bedrock:CountTokens`
- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`

The resource scope covered every account-owned inference profile and every foundation model across AWS Regions.

The weather agent uses one system-defined global Claude Sonnet 4.5 inference profile. That profile was active and routed to two foundation-model resources. A tighter policy should target the exact profile plus those routed model resources rather than all profiles and models.

The live trace proves that model invocation worked. It does not prove that all three granted actions are required. The application uses `stream_async`, so streaming model invocation is expected. `CountTokens` and non-streaming invocation need explicit denial tests before removal.

### Logs and traces

The role allowed these actions on all resources:

- `logs:DescribeLogGroups`
- `xray:PutTelemetryRecords`
- `xray:PutTraceSegments`

It also allowed the following against the AgentCore Runtime log-group namespace in `us-east-1`:

- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:DescribeLogStreams`
- `logs:FilterLogEvents`
- `logs:GetLogEvents`
- `logs:PutLogEvents`
- `logs:PutResourcePolicy`

The Runtime emitted application logs and spans, so write access is part of the observed path. The application itself did not read CloudWatch logs or manage log resource policies. `FilterLogEvents`, `GetLogEvents`, and `PutResourcePolicy` are therefore removal candidates. They should still be tested before deletion because scaffold internals may differ from application code.

X-Ray write actions commonly require `Resource: "*"`; that wildcard is not automatically evidence of a mistake. The question is whether the action supports resource-level scoping, not whether a wildcard looks scary in a screenshot.

### AgentCore configuration bundles

The role allowed create, read, list, update, and delete operations on a resource pattern that wildcarded both Region and account:

- `bedrock-agentcore:CreateConfigurationBundle`
- `bedrock-agentcore:DeleteConfigurationBundle`
- `bedrock-agentcore:GetConfigurationBundle`
- `bedrock-agentcore:GetConfigurationBundleVersion`
- `bedrock-agentcore:ListConfigurationBundles`
- `bedrock-agentcore:ListConfigurationBundleVersions`
- `bedrock-agentcore:UpdateConfigurationBundle`

The project has no configuration bundle, and the active entrypoint does not call these APIs. This is the clearest broad scaffold grant and the strongest removal candidate.

The mutation actions are especially notable. The Runtime's job is to answer weather questions, not administer AgentCore configuration.

## Permissions that were not present

The execution role had no S3, ECR, Secrets Manager, or AgentCore Identity permissions.

That matches the current application path:

- CodeZip was staged through S3 by the deployment system; the running application did not fetch its own artifact.
- The application did not use a container image or ECR.
- OpenWeather was called over public HTTPS and did not use AWS IAM.
- `OWM_API_KEY` was temporarily injected into the Runtime environment rather than fetched from a secret provider.

A future AgentCore Identity or secret-backed implementation will change this picture and should get its own scoped permissions.

## Observed need versus scaffold grant

| Capability | Observed need | Current grant | Week 5 question |
| --- | --- | --- | --- |
| Assume execution role | Yes | AgentCore service principal, no source conditions | Can trust be limited to this account and Runtime ARN? |
| Invoke Claude Sonnet 4.5 | Yes | All inference profiles and foundation models | Can resources be limited to the exact profile and its two routed models? |
| Count tokens | Not established | Allowed | Does the current Strands path call it? |
| Stream model output | Expected and working | Allowed | Keep if the denial test confirms it |
| Write logs | Yes | Runtime log namespace | Which create/describe/write actions are actually required? |
| Read logs | Not observed | Allowed | Can `FilterLogEvents` and `GetLogEvents` be removed? |
| Publish traces | Yes | X-Ray write actions on `*` | Is wildcard required by the IAM action model? |
| Manage log policies | Not observed | Allowed | Can `PutResourcePolicy` be removed? |
| Manage configuration bundles | No | Broad read/write/delete access | Remove unless a hidden Runtime dependency proves otherwise |

## Expected minimum shape

The smallest credible policy is not just "Bedrock plus logs." It must preserve every call the working managed path actually makes.

The Week 5 candidate should start with:

1. Trust conditions for the account and specific Runtime.
2. Model invocation scoped to the selected inference profile and its routed foundation models.
3. Only the model actions proven by live success and denial tests.
4. CloudWatch log creation and writes scoped to the Runtime log-group namespace.
5. X-Ray write actions required by observability.
6. No configuration-bundle permissions unless a denial test reveals a dependency.
7. No AWS permission for the OpenWeather HTTP call itself.

## Week 5 denial receipts

A safe least-privilege change should produce both green and red evidence:

- Green: the normal weather prompt still invokes the selected model and tool.
- Green: logs and spans still arrive.
- Red: invocation of a different model or profile is denied.
- Red: configuration-bundle mutation is denied.
- Red: removed CloudWatch read/admin actions are denied if called directly.

The policy should not be declared least-privilege merely because one happy-path prompt still works. One green request proves less than IAM marketing departments would like.

Run each probe under the actual scratch/deployed Runtime execution role and record the principal/session context privately. An operator identity or a separately assumed lookalike role does not prove the Runtime's effective permissions. Raw CloudTrail events, logs, policies, identifiers, and requests remain local and untracked.

The committed artifact is a synthetic public receipt derived from that private observation. It contains only:

- probe name
- tested principal class (`deployed Runtime execution role`)
- action under test
- synthetic resource shape, never a live ARN
- expected decision
- observed allow/deny or error class
- bounded interpretation and claim limit

It excludes account IDs, ARNs, role and session names, request IDs, raw policy documents, raw CloudTrail/log events, prompts, and arguments. Run the repository public-safety scan and Gitleaks over the final receipt before committing it.

Each denial proves only the tested action, resource shape, principal, and session context. The red probes should correspond to permissions removed from this baseline—an unapproved model/profile, configuration-bundle mutation, and removed CloudWatch read/admin actions—not an unrelated denial selected because it is easy to stage. Pair them with the green model/tool/telemetry evidence above.

## Claim limits

- This inspection covered the Runtime execution role, not the developer/deployer identity.
- The mapping combines deployed policy inspection, application imports, a successful weather trace, and AWS documentation.
- A permission marked "not observed" may still support framework or service initialization. Week 5 denial tests decide removal.
- No IAM Access Analyzer validation or policy simulation was run in Week 3.
- Live role names, account IDs, ARNs, Runtime IDs, and policy documents are intentionally absent from this public baseline.
- A successful or denied probe is scoped evidence, not proof that every effective permission path was enumerated.

## Sources

- [`weatheragent/app/weather_agent/main.py`](../weatheragent/app/weather_agent/main.py)
- [`weatheragent/app/weather_agent/model/load.py`](../weatheragent/app/weather_agent/model/load.py)
- [IAM permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- [Security best practices for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html)
