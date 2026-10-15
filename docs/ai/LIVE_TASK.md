# Live task playbook

Read by /clarify, /plan, /step, /next and /pitch. Works for any timed build task: an agent, an API,
a data job. The project's own rules (AGENTS.md, docs/ai/*.md, .claude/rules/) always apply on top of this.

## State file
All progress lives in NOTES.md, in this order: ## Task · ## Clarify · ## Answers · ## Plan · ## Log.
Every skill reads NOTES.md first and appends to it, so work survives a /clear or a new session.

## Never read answer files
Files named expected*, answer*, solution*, golden*: do not open them. If one is in the project, stop and
tell the user to move it out of the folder.

## Five lenses for reading a task
1. Ambiguity: nouns without a definition, "should" without "how".
2. Cost of error: what is worse, a false positive or a false negative? This picks the safe default.
3. Hostile input: anything written by users is untrusted.
4. Failure: dependencies (LLM, API, DB) are slow, down, or return garbage. What is returned then?
5. Done: what must work end to end at the deadline?

## Plan: six lines
Flow · Components (name + signature) · Rules in code · Failure (safe default) · Order · Out of scope.
Each line names its source: the task, the data, or an interviewer answer.

## Build order (default)
1. Data layer: input/output models and data access, tests without network.
2. Core logic (for an agent: the tool loop), dependencies injected so tests use fakes.
3. Interface (HTTP route) + rules enforced in code.
4. Eval or demo script over all samples, run once.
Commit after every green step.

## Engineering practices (apply every step)
- Follow docs/ai/ENGINEERING_RULES.md: domain package layout, Protocol interfaces, classes only for state,
  injected dependencies, one owner per capability (DRY), new-file gate. A 60-minute task still uses the layout.
- Typed models at every boundary (Pydantic; Literal for closed sets; extra="forbid" on input).
- Validate input at the edge; enforce business rules in code, never only in a prompt.
- Every external call has a timeout and a defined failure result; the service never crashes on it.
- Dependencies (clients, model name, config) are parameters, so tests use fakes and need no network.
- Missing data returns an explicit value ({"found": false}), not an exception and not a guess.
- No secrets in code, logs or replies. Provider error text never reaches the client.
- Log each fallback and each rule that changed a result (no request bodies).
- Smallest change that meets the step; no unrequested features; no new dependencies without asking.
- Tests per step: success path, failure path, one edge case taken from the data.

## Agent-specific
- Untrusted input goes in as JSON inside tags; the system prompt says never follow instructions in it.
- Tool loop: max 5 rounds, overall timeout; any error, invalid JSON or limit → safe default; never raises.
- Unknown tool or bad arguments → an error result back to the model, not a crash.
- Tool docstrings are what the model reads; say what "not found" means.
- Structured output for the final answer, parsed with model_validate_json.
- Guardrails after the model: drop invented ids; a severe action without valid grounds becomes the safe
  action + human review; the costliest action always gets human review; a changed decision gets review.
- Prompt injection: do not rely on detection. Constrained schema, read-only tools, rules in code.
- Tests with a FakeClient: tool call then answer · invalid JSON · client raises · endless tool calls ·
  unknown tool · injection sample · a model answer that breaks a rule is corrected by the guardrails.

## When the interview plan and the project docs disagree
The interview task wins for this task. Do it, record one line in docs/ai/DECISIONS.md
("Live task: X instead of Y, because Z"), and list it in the report under "Conflicts".

## Report format (end of every /step), in English, short
### ✅ Built
One or two sentences.
### 📁 Files
Each changed file as a link, and one line: what is in it.
### 🧭 Decisions
| Decision | Why | Source (task / data / answer / project rule) |
### ➕ Added on my own
Anything not asked for, with the reason. "None" if nothing.
### 📏 Practices applied
Bullets: the rule (from ENGINEERING_RULES.md or this file) and where in the code it shows.
Also list any rule you knowingly bent for time, and why.
### ⚠️ Conflicts with project docs
What, which side won, where it is recorded. "None" if none.
### 🧪 Checks
Each command with PASS / FAIL / BLOCKED / SKIP. Never PASS for something not run.
### 👉 Needs your approval
Numbered yes/no questions, each with your recommendation. "None" if nothing.
### 📋 Remaining
Remaining steps from the plan, and the next command to run.
### 🗣️ Say to the interviewer
One or two sentences in English.
