# Engineering rules

Adapted from the RagForge engineering rules for a FastAPI + LLM agent service.
`.claude/rules/architecture.md` points here for every file under `app/`.

## Project layout
One package per domain. A new feature gets its own package; shared code moves out only when two domains
really share it.

    app/
      main.py            lifespan (creates clients once), router wiring
      config.py          Settings (pydantic-settings); every option changes real behavior
      errors.py          the one error shape
      routes/<domain>.py thin: validate, call the service, shape the response
      providers/         LLM provider Protocol + one class per provider (OpenAI, ...)
      <domain>/
        models.py        Pydantic models at the boundary (request, response, tool args)
        service.py       orchestrates the use case; routes call only this
        agent.py         the model loop for this domain
        tools.py         tool functions + registry (or repository.py when it owns state/data access)
        guardrails.py    business rules enforced in code after the model
    tests/               mirrors app/: tests/<domain>/test_<module>.py

## Object-oriented design
- Prefer `typing.Protocol` for interfaces (for example `LLMProvider`, `Repository`); use ABC inheritance
  only when behavior or lifecycle inheritance is meaningful.
- Classes (or dataclasses) for state, lifecycle, resources, policies and repositories:
  a provider holding a client, a repository holding loaded data, a guardrail policy with configuration.
- Pure calculations stay pure functions. No "manager" class around stateless functions.
- Dependencies are injected through constructors or parameters (client, provider, repository, settings),
  never created inside the class or at import time. This is what makes fakes in tests trivial.
- Composition over inheritance. Keep inheritance trees one level deep.
- One class or module = one responsibility you can state in one sentence.

## DRY and one owner per capability
- Each capability has one authoritative implementation: model calls, tool registry, config, error shape,
  data loading. Before adding code, search for the existing owner and extend it.
- No parallel paths ("legacy + v2"). When new code replaces old code, migrate callers and delete the old path.
- Shared constants and schemas live in one place and are imported, never copied.
- Do not abstract on the first repetition. Extract on the second real duplicate, into the domain that owns it.

## New-file gate
Before creating a production file:
1. Search for the existing owner of this capability.
2. State the file's responsibility in one sentence.
3. Prefer extending the owner.
4. Use a domain name (`url_reputation.py`, `review_policy.py`). Never `utils`, `helpers`, `manager`,
   `misc`, `common`, `v2`.

## Size ratchet (a review signal, not a rule to split blindly)
- New file over 400 lines: justify it as one responsibility. Over 600: do not create it without approval.
- New or touched function over 80 lines: look for a cohesive extraction. Over 150: needs a justification.

## Python
- Type hints on all new and touched code: `dict[str, T]`, `X | None`.
- Pydantic at transport and config boundaries; `Literal` for closed sets; `extra="forbid"` on input models.
- Catch specific exceptions. Never swallow `asyncio.CancelledError`.
- No network or file I/O at import time, except loading small static reference data deliberately.

## FastAPI and async
- Clients are created and closed in the lifespan and injected; no module-level globals.
- Routes validate, authorize and dispatch; business logic lives in services.
- No blocking I/O on async paths. Bound fan-out with a semaphore. Every network call has a timeout.
- Timeouts and cancellation propagate; no zombie work.

## AI
- Model output, tool arguments and user content are untrusted.
- Business rules are enforced in code, not only in the prompt.
- Keep production logic free of eval/golden expected labels.
- `null` means unmeasured. Rates come with their denominator. An LLM judge is a proxy, not truth.
- Version prompt, model and dataset when you report eval numbers.

## Refactoring and comments
- Behavior-neutral cleanup only inside the scope you are already touching; no unrelated rewrites,
  no speculative frameworks, at most 2 new production modules per task unless the task needs more.
- Comments explain why and state invariants (security, concurrency, delivery, eval semantics).
  Delete comments that narrate the code.
