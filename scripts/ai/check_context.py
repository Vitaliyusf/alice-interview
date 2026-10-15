#!/usr/bin/env python3
# ruff: noqa: E501, RUF100  (long help strings; copied into projects with other line lengths)
"""Check the agent instruction files: size, dead paths, placeholders, rules, skills, tasks, secrets, gitignore.

    python scripts/ai/check_context.py            errors fail, warnings are printed
    python scripts/ai/check_context.py --strict   warnings fail too (use after SETUP-01)

Standard library only, so it runs on Windows, macOS, Linux and CI without installing anything.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "docs" / "ai"
TASKS = AI / "tasks"

MAX_AGENTS_LINES, MAX_AGENTS_BYTES = 150, 9000
MAX_CLAUDE_LINES = 40
TASK_WARN_LINES, TASK_MAX_LINES = 80, 200
TEMPLATES = {"TASK_TEMPLATE.md", "HANDOFF_TEMPLATE.md"}

PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
TASK_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z]?$")
PATH_LIKE = re.compile(
    r"^\.?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+$|^[A-Za-z0-9_.-]+\.(?:md|py|json|toml|ya?ml|txt)$"
)
SECRETS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}"),
]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else None


def git_ignored(path: str) -> bool | None:
    """True or False inside a git repository, None when git or the repository is missing."""
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if inside.returncode != 0:
            return None
        return (
            subprocess.run(["git", "check-ignore", "-q", "--", path], cwd=ROOT, check=False).returncode == 0
        )
    except OSError:
        return None


def check_entry_files(r: Report) -> None:
    agents, claude = ROOT / "AGENTS.md", ROOT / "CLAUDE.md"
    if not agents.exists():
        r.error("AGENTS.md is missing")
    else:
        text = read(agents)
        lines = len(text.splitlines())
        if lines > MAX_AGENTS_LINES or len(text.encode()) > MAX_AGENTS_BYTES:
            r.error(
                f"AGENTS.md is {lines} lines / {len(text.encode())} bytes; limit {MAX_AGENTS_LINES} / {MAX_AGENTS_BYTES}"
            )
        if re.search(r"(?i)\bsupersed", text):
            r.warn(
                "AGENTS.md says 'supersede': fix the original rule instead of adding an overriding section"
            )
    if not claude.exists():
        r.error("CLAUDE.md is missing")
    else:
        text = HTML_COMMENT.sub("", FENCE.sub("", read(claude)))
        if not re.search(r"(?m)^@AGENTS\.md\s*$", text):
            r.error("CLAUDE.md must import AGENTS.md with a line '@AGENTS.md'")
        if len(text.strip().splitlines()) > MAX_CLAUDE_LINES:
            r.error(f"CLAUDE.md is longer than {MAX_CLAUDE_LINES} lines: shared rules belong in AGENTS.md")


def instruction_files() -> list[Path]:
    files = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md"]
    files += sorted(AI.glob("*.md"))
    files += sorted((ROOT / ".claude" / "rules").glob("*.md"))
    files += sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    files += sorted((ROOT / ".claude" / "agents").glob("*.md"))
    return [f for f in files if f.exists()]


def check_paths_and_placeholders(r: Report) -> None:
    for path in instruction_files():
        text = read(path)
        if path.name not in TEMPLATES:
            found = PLACEHOLDER.findall(HTML_COMMENT.sub("", text))
            if found:
                r.warn(f"{rel(path)}: {len(found)} unfilled placeholder(s), first: {found[0][:50]}")
        for token in CODE_SPAN.findall(FENCE.sub("", text)):
            token = token.strip().rstrip(".,:")
            if any(ch in token for ch in "<>{}*$ ") or not PATH_LIKE.match(token):
                continue
            if token.startswith((".agent-private", "http")) or token.count(".") > 3:
                continue
            if "/" not in token:
                continue  # a bare file name may be relative to its folder or just a name in prose
            if not (ROOT / token.split("/")[0]).is_dir():
                continue  # "fix/some-branch" or "1/2/4": not a path inside this repository
            if not (ROOT / token).exists() and not (path.parent / token).exists():
                r.error(f"{rel(path)}: refers to `{token}`, which does not exist")


def check_rules_and_skills(r: Report) -> None:
    for path in sorted((ROOT / ".claude" / "rules").glob("*.md")):
        fm = frontmatter(read(path))
        if fm is None or not re.search(r"(?m)^paths:\s*$", fm):
            r.warn(f"{rel(path)}: no `paths` frontmatter, so it loads in every session")
    for path in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        fm = frontmatter(read(path))
        if fm is None or not re.search(r"(?m)^description:\s*\S", fm):
            r.error(f"{rel(path)}: frontmatter needs a `description` (it tells Claude when to use the skill)")
    for path in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        fm = frontmatter(read(path))
        if (
            fm is None
            or not re.search(r"(?m)^name:\s*\S", fm)
            or not re.search(r"(?m)^description:\s*\S", fm)
        ):
            r.error(f"{rel(path)}: a subagent needs `name` and `description` in its frontmatter")
    settings = ROOT / ".claude" / "settings.json"
    if settings.exists():
        try:
            json.loads(read(settings))
        except json.JSONDecodeError as exc:
            r.error(f".claude/settings.json is not valid JSON: {exc}")


def check_tasks(r: Report) -> None:
    index = TASKS / "INDEX.md"
    if not index.exists():
        r.error("docs/ai/tasks/INDEX.md is missing")
        return
    index_text = read(index)
    listed = set(re.findall(r"(?m)^\|\s*([A-Z][A-Z0-9-]*\d+[A-Z]?)\s*\|", index_text))
    active = {}
    for path in sorted(TASKS.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        task_id = path.stem
        text = read(path)
        lines = len(text.splitlines())
        if not TASK_ID.match(task_id):
            r.warn(f"{rel(path)}: file name is not a task id like AREA-01")
        status = re.search(r"(?m)^Status:\s*(\w+)", text)
        if not status:
            r.error(f"{rel(path)}: no 'Status:' line")
        elif status.group(1) == "done":
            r.error(f"{rel(path)}: status is done; move it to docs/ai/tasks/done/")
        if lines > TASK_MAX_LINES:
            r.error(f"{rel(path)}: {lines} lines; split the task (limit {TASK_MAX_LINES})")
        elif lines > TASK_WARN_LINES:
            r.warn(f"{rel(path)}: {lines} lines; a task file should fit in {TASK_WARN_LINES}")
        active[task_id] = path
    for task_id in sorted(set(active) - listed):
        r.error(f"{task_id} has a task file but no row in docs/ai/tasks/INDEX.md")
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "ai"))
        import kit  # the same folder

        if not kit.index_is_current():
            r.warn("docs/ai/tasks/INDEX.md does not match the task files: python scripts/ai/kit.py index")
    except ImportError:
        pass
    done_ids = {p.stem for p in (TASKS / "done").glob("*.md")}
    for task_id in sorted(listed - set(active) - done_ids):
        r.error(
            f"INDEX.md lists {task_id}, but neither tasks/{task_id}.md nor tasks/done/{task_id}.md exists"
        )


def check_secrets(r: Report) -> None:
    files = instruction_files() + sorted(TASKS.rglob("*.md"))
    for path in files:
        text = read(path)
        for pattern in SECRETS:
            if pattern.search(text):
                r.error(f"{rel(path)}: looks like it contains a secret ({pattern.pattern[:30]}...)")
                break


def check_hygiene(r: Report) -> None:
    for path in sorted(AI.rglob("*")):
        if path.is_file() and re.search(r"(?i)[_-]v\d+(?:[_.]\d+)*\.", path.name):
            r.warn(f"{rel(path)}: version suffix in a file name; keep one current file, git has the history")
    for name in (".agent-private/", "CLAUDE.local.md"):
        ignored = git_ignored(name)
        if ignored is False:
            r.error(f"{name} is not ignored by git; add it to .gitignore")
        elif ignored is None:
            r.warn("not a git repository: could not check .gitignore")
            break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    r = Report()
    for check in (
        check_entry_files,
        check_paths_and_placeholders,
        check_rules_and_skills,
        check_tasks,
        check_secrets,
        check_hygiene,
    ):
        check(r)

    for msg in r.errors:
        print(f"ERROR  {msg}")
    for msg in r.warnings:
        print(f"WARN   {msg}")
    failed = bool(r.errors) or (args.strict and bool(r.warnings))
    print(
        f"\nAgent context: {'FAIL' if failed else 'PASS'} ({len(r.errors)} errors, {len(r.warnings)} warnings)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
