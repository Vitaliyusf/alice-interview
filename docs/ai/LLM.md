# LLM and agent rules

Read this before changing `app/agent.py` or anything that calls the model.

## OpenAI Responses API: use exactly these shapes (not Chat Completions)

- Call: `await client.responses.create(model=..., instructions=SYSTEM, input=items, tools=tool_specs())`.
- A tool spec is flat: `{"type": "function", "name": ..., "description": ..., "parameters": <JSON Schema>, "strict": True}`.
  Strict mode needs every property listed in `"required"` and `"additionalProperties": False`.
- A tool call is an item in `response.output` with `.type == "function_call"`, `.name`, `.arguments` (a JSON string)
  and `.call_id`.
- To continue: first `items += response.output` (the model's own items, unchanged), then for EVERY call append
  `{"type": "function_call_output", "call_id": call.call_id, "output": <string>}`.
- No `function_call` items in the reply means `response.output_text` is the final answer. It can be empty or
  cut off: `response.status` says `"incomplete"` for a cut-off reply.
- Structured final answer: `text={"format": {"type": "json_schema", "name": ..., "schema": ..., "strict": True}}`.
- The client is created once in `app/main.py` with a timeout and retries. Do not create another one.

## Agent rules

- `TOOLS` is the registry and the allowlist. Each entry is a `Tool` dataclass (the argument model and the
  function); a new per-tool flag is a new field with a default. Tool arguments are a Pydantic model with
  `extra="forbid"`.
- `run_tool` never raises: an unknown tool, bad arguments, a timeout and a crash all come back as
  `{"ok": False, "error": ...}`. Exception text and stack traces go to the log, never to the model.
  Validation messages (field: message) may go back, so the model can correct its call.
- Everything the model writes (tool name, arguments, URLs, SQL) and everything a tool returns is untrusted input.
- The files in `data/` are fixtures. A tool that changes data keeps the change in memory; no tool and no test
  rewrites those files.
- The loop has a hard step limit and returns an explicit status for every way it can end.
- A new run status is added to `RunResult` and to the `Literal` in `AskResponse`. It is returned as HTTP 200
  with that status unless I say otherwise. HTTP errors are for failures of the service, not of the agent.
- An `OpenAIError` from the model call is not caught in the loop: it propagates to the handlers in `app/errors.py`.

## Tests

`tests/conftest.py` has `FakeOpenAI`: `will_say(text, status=, usage=)`, `will_call((name, args), ...)`,
`will_raise(error)`. It rejects keywords the real SDK does not accept. Assert on `fake_openai.requests[i]`,
which holds a snapshot of what was sent.
