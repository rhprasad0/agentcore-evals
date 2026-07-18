# Week 16 — Capstone Incident Drill and Controlled Closeout

**Prerequisite:** The capped hosted demo is live, drift-free, and protected by tested Guardrail, WAF, daily-cap, kill-switch, alarm, and Budget controls.

[← Week 15](week-15-hosted-demo.md) · [Week index](README.md)

## Concept

Practice two different recovery loops and keep their mechanisms honest:

- **application rollback:** change PROD's pinned immutable Runtime version; and
- **infrastructure recovery:** restore known-good declarative HCL/artifact inputs and apply the resulting diff.

Terraform has no CloudFormation-style automatic stack rollback. Restoring an old versioned S3 state object is break-glass recovery for actual state corruption—not a shortcut for ordinary bad-resource recovery. The project closes with a production-shaped learning system and receipts, not a production-readiness claim.

## Build

### 1. Predeclare both drills

Before fault injection, write:

- failure hypotheses and expected alarms;
- first trace/log queries and kill criterion;
- previous known-good Runtime version;
- known-good Git/HCL/artifact revision;
- current Terraform state object version;
- rollback/recovery commands and expected plans;
- recovery criteria; and
- stop conditions.

Lower the public daily limit, verify WAF and both Guardrail paths, test the kill switch, acquire the Terraform lock, and prove the starting plan has no unexpected drift. Never run both faults at once.

### 2. Drill Runtime endpoint-version rollback

Create one controlled bad Runtime version that causes an observable two-tool regression or application error. Package and apply it to STAGING, verify the fault, then promote that explicit version to PROD only through a reviewed endpoint plan.

Execute and timestamp:

1. alarm received;
2. trace/log diagnosis identifies the bad Runtime version;
3. kill switch disables new Runtime calls;
4. `release.tf` restores the previous approved immutable version;
5. an endpoint-only Terraform plan is reviewed and applied;
6. one controlled verification passes; and
7. public traffic is re-enabled.

Capture detection, acknowledgement, mitigation, rollback, and recovery times. Do not change unrelated infrastructure during this drill.

### 3. Drill known-good Terraform configuration recovery

After closing the Runtime incident, apply one separate, reversible, valid-but-bad infrastructure change—such as an intentionally over-restrictive demo WAF threshold—that causes a bounded canary to fail without weakening security or touching state storage.

Diagnose the exact HCL/resource delta from the saved plan, keep the public kill switch off, restore the known-good reviewed HCL revision, generate a new recovery plan, apply it, verify the canary, and finish with a no-drift plan.

Do not use `terraform state` surgery, force-unlock an active owner, perform an unreviewed apply, or manufacture a partial-apply failure for drama.

### 4. Close the incident record and runbook

Create `docs/reports/week-16-incident-drill.md` with timeline, alarm evidence, diagnosis, kill action, endpoint rollback, HCL recovery, verification, and lessons. Finalize `docs/runbooks/production-demo.md` from commands that actually worked.

Update the README capstone state only with verified links: live demo, Week 8 baseline, eight-row human/custom/managed report, governed Gateway denials, reliability, operations, red/green CI, and both recovery receipts.

### 5. Confirm the keep-live contract and teardown fallback

Verify and record an owner/date for the next monthly review plus:

- 10 Runtime calls/day;
- working `enabled` kill switch;
- one WAF rate rule;
- two actionable alarms;
- existing `$10` Terraform Budget;
- named PROD endpoint;
- remote locked/versioned state; and
- exact emergency disable/destroy and resource-absence checks.

Normal closeout leaves the bounded demo live. Emergency teardown destroys only the production-demo root; state-bootstrap and Budget remain. Destroy the bootstrap only after every surviving state key, including Budget, has moved elsewhere or been intentionally destroyed.

## Deliverable

One incident/closeout artifact group:

- `docs/reports/week-16-incident-drill.md`
- finalized `docs/runbooks/production-demo.md`
- verified README capstone links
- recorded keep-live review and teardown fallback

There is no optimizer trial, multi-agent architecture, fake uptime claim, or third incident scenario.

## Success check

Both drills restore a known-good service through reviewed Terraform plans; receipts alone reconstruct who/what/when; the final plan is drift-free; the runbook matches executed commands; keep-live controls and monthly review are verified; and the write-up clearly distinguishes a production-shaped learning system from a production-ready service.

## Read

- [AgentCore Runtime versioning](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html)
- [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [CloudFront continuous operations guidance](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-values-specify.html)
- [Week 13 Runtime operations](week-13-runtime-operations.md)