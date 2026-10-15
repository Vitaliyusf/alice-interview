@AGENTS.md

## Claude Code only

- Path rules in `.claude/rules/` load when you work on matching files. Follow them.
- For a wide search, use a subagent and bring back paths and symbols, not search transcripts.
- Use plan mode for a change across more than 5 files or any contract change.
- Project skills: `/status`, `/plan-feature`, `/new-task`, `/task <ID>`, `/review-changes`, `/handoff`.
- The `reviewer` subagent reviews a diff in a fresh context. Use it before the final response of any task.
- Create and change files with the Write and Edit tools, never with shell redirects (`cat > file`): the format
  hook and the permission rules only see those tools. If the hook reports an error, fix the syntax problem.
- My personal preferences live in `CLAUDE.local.md` (gitignored), not here.

<!-- Maintainers: keep this file under 40 lines. Shared rules belong in AGENTS.md so Codex sees them too.
     HTML comments like this one are not sent to the model. -->
