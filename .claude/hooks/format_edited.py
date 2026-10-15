#!/usr/bin/env python3
# ruff: noqa: E501, RUF100  (long help strings; copied into projects with other line lengths)
"""Claude Code PostToolUse hook: format the file Claude just edited or wrote.

Reads the hook JSON from stdin and takes `tool_input.file_path`. Picks a formatter by file extension and runs it
only if that formatter is installed. Exit codes follow the Claude Code hook contract:
  0  formatted, or nothing to do (no formatter for this file type, formatter not installed)
  2  the formatter rejected the file (for example a syntax error): stderr is shown to Claude
Never fails the session because of a missing tool. Standard library only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# extension -> command. The file path is appended. Edit this table for your project.
FORMATTERS: dict[str, list[str]] = {
    ".py": ["ruff", "format"],
    ".ts": ["prettier", "--write", "--log-level", "warn"],
    ".tsx": ["prettier", "--write", "--log-level", "warn"],
    ".js": ["prettier", "--write", "--log-level", "warn"],
    ".jsx": ["prettier", "--write", "--log-level", "warn"],
    ".json": ["prettier", "--write", "--log-level", "warn"],
    ".css": ["prettier", "--write", "--log-level", "warn"],
}
TIMEOUT_S = 20


def find_tool(name: str, root: Path) -> str | None:
    """The project's own copy first (node_modules/.bin, .venv), then PATH."""
    for folder in (
        root / "node_modules" / ".bin",
        root / ".venv" / "bin",
        root / ".venv" / "Scripts",
    ):
        found = shutil.which(name, path=str(folder))
        if found:
            return found
    return shutil.which(name)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    file_path = (event.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    path = Path(file_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_file() or root not in path.parents:
        return 0  # only files inside this project
    command = FORMATTERS.get(path.suffix.lower())
    if not command:
        return 0
    tool = find_tool(command[0], root)
    if not tool:
        return 0  # formatter not installed here: nothing to do
    try:
        result = subprocess.run(
            [tool, *command[1:], str(path)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"format hook: {command[0]} did not run: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 0
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()[-1500:]
        print(
            f"{command[0]} could not format {path.relative_to(root)}:\n{message}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
