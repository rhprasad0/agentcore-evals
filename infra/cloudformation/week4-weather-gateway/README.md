# Week 4 weather Gateway stack

This stack exposes the existing current-weather contract through a Lambda target on the already-deployed `eval-gateway`.

## Ownership boundary

CloudFormation owns:

- Lambda and its execution role;
- seven-day log group;
- scoped invoke policy on the existing Gateway role;
- `weather-lambda` Gateway target.

The AgentCore CLI configuration continues to own the Gateway and Web Search connector. The deploy helper discovers account-specific values at runtime and does not write them into tracked files.

## Commands

Run from the repository root with authenticated AWS credentials in `us-east-1`:

```bash
set -a
source .env
set +a
uv run --project weatheragent/app/weather_agent \
  python3 scripts/week4_weather_gateway.py preview

uv run --project weatheragent/app/weather_agent \
  python3 scripts/week4_weather_gateway.py deploy

uv run --project weatheragent/app/weather_agent \
  python3 scripts/week4_weather_gateway.py status
```

The preview creates and removes a CloudFormation change set. Deployment requires `OWM_API_KEY` in the process environment; the helper sends it to a `NoEcho` parameter without printing it.

Run the no-model comparison:

```bash
uv run --project weatheragent/app/weather_agent \
  python3 scripts/compare_week4_weather_seams.py \
  --city Oslo --units metric --samples 3
```

Delete only the comparison stack:

```bash
uv run --project weatheragent/app/weather_agent \
  python3 scripts/week4_weather_gateway.py delete
```

Deletion removes the Lambda target, scoped policy, Lambda, role, and log group. It does not delete the existing Gateway, Web Search connector, Runtime, CDK bootstrap resources, or content-addressed bootstrap-bucket assets.

## Contract sources

- MCP schema: [`../../../schemas/weather-tool.json`](../../../schemas/weather-tool.json)
- Shared pure contract core: [`../../../weatheragent/app/weather_agent/weather_core.py`](../../../weatheragent/app/weather_agent/weather_core.py)
- Lambda transport: [`lambda/lambda_function.py`](lambda/lambda_function.py)
- Direct transport: [`../../../weatheragent/app/weather_agent/weather_tool.py`](../../../weatheragent/app/weather_agent/weather_tool.py)

The deploy helper converts lower-camel MCP schema keys to the PascalCase structure required by the CloudFormation resource provider. It does not rewrite names, descriptions, types, property names, or required fields.

## Credential boundary

The `NoEcho` parameter plus encrypted Lambda environment is a bounded Week 4 compromise. Do not describe it as the final production credential pattern. Week 12 replaces this seam with managed credential storage, rotation, and reliability controls.
