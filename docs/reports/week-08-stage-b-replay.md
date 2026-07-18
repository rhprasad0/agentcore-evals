# Week 8 Stage B Evaluation Report

> This receipt is deterministic offline replay over accepted synthetic fixtures. It is not a fresh Stage A model baseline; it is not a response-quality evaluation; it is not a production benchmark; and it is not a security sandbox.

- Experiment: `sha256:44a9f913a720759748d57647f002b0e924d39b38b65a2fdfbe713774bfc2cca5`
- Fixture set: `evals.weather_only_regression`
- Source run: `5a10e0ab-93dc-4e4f-99d6-73dfa3397e9c`
- Counts: `{"evidenceValidCases": 60, "gateErrors": 0, "instrumentErrors": 2, "projectedCases": 62}`

## Overall metrics

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 60 | 55 | 60 | 0.916667 | 0 | 0 |
| parameter | tool-call | 54 | 52 | 54 | 0.962963 | 0 | 0 |
| execution | tool-call | 66 | 48 | 66 | 0.727273 | 0 | 0 |
| failureBehavior | case | 14 | 12 | 14 | 0.857143 | 0 | 0 |
| noTool | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 62 | 60 | 62 | 0.967742 | 2 | 0 |

## By tag

### `ambiguity`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 3 | 3 | 3 | 1.000000 | 0 | 0 |
| parameter | tool-call | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| execution | tool-call | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 4 | 3 | 4 | 0.750000 | 1 | 0 |
### `comparison`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| parameter | tool-call | 32 | 30 | 32 | 0.937500 | 0 | 0 |
| execution | tool-call | 32 | 32 | 32 | 1.000000 | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
### `decline`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 4 | 4 | 4 | 1.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 4 | 4 | 4 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 4 | 4 | 4 | 1.000000 | 0 | 0 |
### `dependency`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| parameter | tool-call | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| execution | tool-call | 2 | 0 | 2 | 0.000000 | 0 | 0 |
| failureBehavior | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
### `direct-answer`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 9 | 9 | 9 | 1.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 9 | 9 | 9 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 10 | 9 | 10 | 0.900000 | 1 | 0 |
### `forced-choice`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| parameter | tool-call | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| execution | tool-call | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 1 | 1 | 1 | 1.000000 | 0 | 0 |
### `near-boundary`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 17 | 15 | 17 | 0.882353 | 2 | 0 |
### `no-fabrication`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 14 | 9 | 14 | 0.642857 | 0 | 0 |
| parameter | tool-call | 6 | 6 | 6 | 1.000000 | 0 | 0 |
| execution | tool-call | 18 | 0 | 18 | 0.000000 | 0 | 0 |
| failureBehavior | case | 14 | 12 | 14 | 0.857143 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 14 | 14 | 14 | 1.000000 | 0 | 0 |
### `non-retryable`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 5 | 3 | 5 | 0.600000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 3 | 0 | 3 | 0.000000 | 0 | 0 |
| failureBehavior | case | 5 | 3 | 5 | 0.600000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 5 | 5 | 5 | 1.000000 | 0 | 0 |
### `retryable`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 7 | 4 | 7 | 0.571429 | 0 | 0 |
| parameter | tool-call | 4 | 4 | 4 | 1.000000 | 0 | 0 |
| execution | tool-call | 13 | 0 | 13 | 0.000000 | 0 | 0 |
| failureBehavior | case | 7 | 7 | 7 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 7 | 7 | 7 | 1.000000 | 0 | 0 |
### `single-tool`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| parameter | tool-call | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| execution | tool-call | 15 | 15 | 15 | 1.000000 | 0 | 0 |
| failureBehavior | case | 0 | 0 | 0 | null | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 15 | 15 | 15 | 1.000000 | 0 | 0 |
### `stop-on-failure`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| parameter | tool-call | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| execution | tool-call | 2 | 0 | 2 | 0.000000 | 0 | 0 |
| failureBehavior | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
### `weather`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 46 | 41 | 46 | 0.891304 | 0 | 0 |
| parameter | tool-call | 54 | 52 | 54 | 0.962963 | 0 | 0 |
| execution | tool-call | 66 | 48 | 66 | 0.727273 | 0 | 0 |
| failureBehavior | case | 14 | 12 | 14 | 0.857143 | 0 | 0 |
| noTool | case | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| instrumentValidity | case | 46 | 46 | 46 | 1.000000 | 0 | 0 |

## By failure kind

### `auth`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 2 | 0 | 2 | 0.000000 | 0 | 0 |
| failureBehavior | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
### `bad_input`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 1 | 0 | 1 | 0.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| failureBehavior | case | 1 | 0 | 1 | 0.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 1 | 1 | 1 | 1.000000 | 0 | 0 |
### `network`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 2 | 0 | 2 | 0.000000 | 0 | 0 |
| failureBehavior | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
### `timeout`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 3 | 1 | 3 | 0.333333 | 0 | 0 |
| parameter | tool-call | 5 | 5 | 5 | 1.000000 | 0 | 0 |
| execution | tool-call | 8 | 0 | 8 | 0.000000 | 0 | 0 |
| failureBehavior | case | 3 | 3 | 3 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 3 | 3 | 3 | 1.000000 | 0 | 0 |
### `upstream_4xx`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 4 | 3 | 4 | 0.750000 | 0 | 0 |
| parameter | tool-call | 0 | 0 | 0 | null | 0 | 0 |
| execution | tool-call | 3 | 0 | 3 | 0.000000 | 0 | 0 |
| failureBehavior | case | 4 | 3 | 4 | 0.750000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 4 | 4 | 4 | 1.000000 | 0 | 0 |
### `upstream_5xx`

| Metric | Unit | Eligible | Numerator | Denominator | Rate | Instrument errors | Gate errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection | case | 2 | 1 | 2 | 0.500000 | 0 | 0 |
| parameter | tool-call | 1 | 1 | 1 | 1.000000 | 0 | 0 |
| execution | tool-call | 3 | 0 | 3 | 0.000000 | 0 | 0 |
| failureBehavior | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |
| noTool | case | 0 | 0 | 0 | null | 0 | 0 |
| instrumentValidity | case | 2 | 2 | 2 | 1.000000 | 0 | 0 |

> Mechanical contract compliance only; response quality is out of scope until human labels exist (Week 9).
