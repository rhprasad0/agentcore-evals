# Week 15 — Capped Terraform-Owned Hosted Demo

**Prerequisite:** PROD points to an approved immutable Runtime version; operations alarms work; the same-evidence report and red/green CI receipt are complete.

[← Week 14](week-14-managed-evaluation-ci.md) · [Week index](README.md) · [Next: Week 16 →](week-16-capstone.md)

## Concept

Expose the governed PROD endpoint through the smallest anonymous browser surface whose cost and shutdown behavior are explicit. CloudFront is the only public entry. A private S3 bucket serves one vanilla page, and an IAM-protected Lambda Function URL receives signed CloudFront origin requests for `/api/*`.

Controls have separate scopes: the proxy Bedrock Guardrail screens browser input/final output; the daily counter bounds Runtime invocations; the kill switch disables them; WAF slows abusive request rates; alarms notify; the Budget warns about account spend. None is an account-wide hard spending or safety guarantee.

## Build

### 1. Create the public edge in Terraform

Add:

- `demo/index.html`: vanilla HTML with inline CSS/JS and one free-form prompt box;
- `web.tf`: private S3 UI bucket, Block Public Access, CloudFront OAC, distribution, `/api/*` behavior, IAM-protected Lambda Function URL origin, source-distribution-scoped Lambda resource policy, one WAF Web ACL/rate rule, demo-control DynamoDB table, IAM, logs, and metrics;
- `guardrail.tf`: one Bedrock Guardrail for proxy input/output, distinct from Week 11's native AgentCore Policy checks; and
- `lambda/proxy.py`: the bounded request/control/Runtime path.

CloudFront OAC signs every Lambda-origin request with SigV4. The Function URL uses `AWS_IAM`; its resource policy accepts only the one distribution. Restrict CORS to the CloudFront origin. Direct S3 and direct Function URL access must fail.

Do not add a web framework, API Gateway, Cognito, managed WAF bundles, bot-control product, or general chat backend.

### 2. Enforce proxy order, cap, and least privilege

For each request, the proxy must:

1. validate the exact JSON shape and bounded one-turn prompt length;
2. read the `enabled` control item;
3. call `ApplyGuardrail` with `INPUT` and reject before Runtime when blocked;
4. atomically increment the current UTC-day Runtime counter only while below `10`;
5. return a clear disabled/limit response without invoking Runtime when blocked;
6. invoke the named PROD endpoint—not DEFAULT/latest;
7. call the same proxy Guardrail with `OUTPUT` before returning content; and
8. return only the answer and an allowlisted normalized tool summary.

Log request IDs, decisions, duration, and error classes—not prompt/response bodies, provider payloads, trace payloads, ARNs, or credentials. Grant only ApplyGuardrail, named PROD invocation, logging, and demo-control item access.

Keep the public control table separate from the weather-breaker table and give each role only its own item operations. Provide an operator command that flips `enabled` immediately.

### 3. Configure WAF and preserve the existing Budget

Attach one measured rate-based WAF rule to CloudFront and test it with a bounded burst. Record the chosen rate and observed block; do not pretend it eliminates abuse.

In the separate existing `infra/terraform/budget/` root, preserve the `$100` limit and the working direct-email 50%/80% actual and 100% forecast notifications; do not expose the destination or recreate a retired notification path. Apply and verify this root separately.

Document residual cost: traffic can still incur CloudFront, WAF, Lambda, DynamoDB, and Guardrail charges after Runtime is capped, and WAF has a monthly base charge.

### 4. Connect evidence and test every boundary

The page links to the Week 8 baseline, Week 9 human gold, Week 11 governed Gateway receipt, Week 12 reliability report, Week 13 operations view, and Week 14 same-evidence/CI results.

Run bounded checks for normal weather→calculator, direct-origin denials, input canary block, explicit output canary block, normal output-check execution, `enabled=false`, a temporary one-call daily limit, WAF rate block, and `$100` Budget readback. Then run a harmless PROD canary and inspect proxy logs plus `aws/spans`; public launch blocks if raw anonymous request/response bodies appear.

Require no-surprise repeat plans for the production-demo and Budget roots.

## Deliverable

One hosted-demo artifact group:

- `demo/index.html`
- Terraform `web.tf` and `guardrail.tf` plus `lambda/proxy.py`
- updated existing Budget root
- `docs/reports/week-15-demo.md` with URL, controls, receipts, monthly review, and teardown fallback

## Success check

An anonymous browser reaches the private-bucket UI and completes a weather→calculator request through CloudFront and named PROD while direct origins fail; output is allowlisted and sampled logs/spans contain no raw bodies; input/output Guardrail checks are proven; kill switch, temporary cap, and WAF each block without unintended Runtime calls; the existing Terraform Budget reads `$100`; and both roots finish with no unexpected drift.

## Read

- [Invoke AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html)
- [Bedrock ApplyGuardrail API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html)
- [CloudFront OAC for Lambda Function URLs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html)
- [AWS WAF rate-based rules](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)