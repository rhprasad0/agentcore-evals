# Hello Agent Loop Trace

This note captures the first Week 1 Strands run: a tiny agent, one AWS identity tool, and the model-facing transcript that proves the agent used the tool instead of guessing.

## Why this matters

The useful artifact is not that the agent answered an AWS identity question. The useful artifact is that the run produced an inspectable loop: user request, selected tool, tool arguments, tool result, and final answer. That is the raw material for later agent evals.

## Run context

- Script: `src/agents/hello.py`
- Prompt: `Which AWS identity am I running as?`
- Tool involved: `caller_identity`
- Sanitization rule: replace real AWS account IDs and ARNs with `<AWS_ACCOUNT_ID>` and `<AWS_ARN>`.

## Predicted message shape

Before running the script, I expected the conversation history to look like this:

1. `user` — question text
2. `assistant` — tool request / `toolUse`
3. `user` — tool result returned to the model
4. `assistant` — final synthesized answer

That prediction was directionally right. The main thing to notice is that the tool result appears as a `user`-role message in the model-facing transcript, even though the human did not type it.

## Observed message sequence

### 1. User question

**Role:** `user`<br>
**Loop stage:** task / input

```json
{
  "role": "user",
  "content": [
    {
      "text": "Which AWS identity am I running as?"
    }
  ]
}
```

This question requires a tool because the live AWS identity is environment-specific. The model should not know it from training data or guess it from context.

### 2. Assistant selects the tool

**Role:** `assistant`<br>
**Loop stage:** reasoning + tool selection

```json
{
  "role": "assistant",
  "content": [
    {
      "text": "Grabbing the AWS identity using the available tool."
    },
    {
      "toolUse": {
        "toolUseId": "<TOOL_USE_ID>",
        "name": "caller_identity",
        "input": {}
      }
    }
  ]
}
```

`caller_identity` was selectable because the Strands `@tool` decorator exposed the Python function as a model-visible tool. The model saw the tool name, its docstring description, and its no-argument input schema. In other words: the function signature and docstring became part of the agent interface, not just code comments.

### 3. Strands returns the tool result to the model

**Role:** `user`<br>
**Loop stage:** tool execution result

```json
{
  "role": "user",
  "content": [
    {
      "toolResult": {
        "toolUseId": "<TOOL_USE_ID>",
        "status": "success",
        "content": [
          {
            "text": "{\"account\": \"<AWS_ACCOUNT_ID>\", \"arn\": \"<AWS_ARN>\"}"
          }
        ]
      }
    }
  ]
}
```

Key observation: Strands represents the tool result as a `user`-role message in the transcript it sends back to the model. The SDK executed the tool, then fed the result back as the next piece of input so the model could synthesize an answer from real data.

### 4. Assistant synthesizes the answer

**Role:** `assistant`<br>
**Loop stage:** final response synthesis

```json
{
  "role": "assistant",
  "content": [
    {
      "text": "The account is <AWS_ACCOUNT_ID> and the ARN is <AWS_ARN>."
    }
  ]
}
```

The final answer used the tool result. The public-safe version keeps the account ID and ARN scrubbed.

## Refusal probe

I also asked the same agent:

```text
What is the capital of France?
```

Observed behavior:

- The agent answered directly: Paris.
- It did not call `caller_identity`.
- It added a caveat that it is configured as an AWS lab assistant.

Evaluation note:

- **Tool-selection behavior:** pass — no irrelevant AWS identity tool call.
- **Response-boundary behavior:** fail — expected refusal or redirect, not answering the non-AWS question.

This is a useful early example of separating tool correctness from response correctness. The agent made the right tool decision but still violated the intended domain boundary.

## Takeaways

- Tool use is inspectable: the transcript shows which tool was selected, what arguments were passed, whether execution succeeded, and how the model used the result.
- Tool descriptions matter: `@tool` metadata becomes part of the model's decision surface.
- A single run can pass one contract and fail another. Here, the France probe passed the no-tool expectation but failed the refusal expectation.
- This message list is the small version of a later eval trace: selected tool, arguments, status, final answer, and boundary behavior can all become fields we score.

## Recruiter-facing summary

Built and inspected a minimal Strands tool-calling agent. The exercise produced a scrubbed trace showing the model selecting a live AWS identity tool, receiving the tool result, and synthesizing an answer from it. A second probe showed why agent evals need separate checks for tool selection and response boundaries: the agent avoided an irrelevant tool call, but still answered a non-domain question it should have refused.
