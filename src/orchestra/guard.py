"""PreToolUse hook that keeps a worker inside its worktree and away from remotes and system installs.

Claude Code runs this before each matching tool call. Exit code 2 blocks the call and
shows stderr to the worker; exit code 0 allows it.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
SYSTEM_PACKAGE_MANAGERS = {"pacman", "yay", "paru", "apt", "apt-get", "brew"}
FORBIDDEN_GIT_SUBCOMMANDS = {"push", "remote"}
SEGMENT_SEPARATORS = re.compile(r"&&|\|\||[;|\n]")


def check(event: dict, root: Path) -> str | None:
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or root)

    if tool in FILE_TOOLS:
        return _check_path(tool_input.get(FILE_TOOLS[tool], ""), cwd, root)
    if tool == "Bash":
        return _check_command(tool_input.get("command", ""))
    return None


def _check_path(raw: str, cwd: Path, root: Path) -> str | None:
    target = (cwd / raw).resolve()
    if target.is_relative_to(root.resolve()):
        return None
    return f"blocked: {target} is outside the worktree {root}"


def _check_command(command: str) -> str | None:
    for segment in SEGMENT_SEPARATORS.split(command):
        reason = _check_segment(segment.strip())
        if reason:
            return reason
    return None


def _check_segment(segment: str) -> str | None:
    if not segment:
        return None
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    if not tokens:
        return None

    program = Path(tokens[0]).name
    args = tokens[1:]

    if program == "sudo":
        return "blocked: sudo is not allowed for workers"
    if program in SYSTEM_PACKAGE_MANAGERS:
        return f"blocked: system package manager {program} is not allowed; use project-level deps"
    if program in {"npm", "pnpm"} and ({"-g", "--global"} & set(args)):
        return f"blocked: global {program} installs are not allowed"
    if program in {"pip", "pip3"} and "--user" in args:
        return "blocked: pip --user installs are not allowed"
    if program == "git":
        subcommand = _git_subcommand(args)
        if subcommand in FORBIDDEN_GIT_SUBCOMMANDS:
            return f"blocked: git {subcommand} is reserved for the orchestrator"
    return None


def _git_subcommand(args: list[str]) -> str | None:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-C", "-c", "--git-dir", "--work-tree"}:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return arg
    return None


def main() -> int:
    root = Path(os.environ.get("ORCHESTRA_WORKTREE_ROOT") or os.getcwd())
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = check(event, root)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
