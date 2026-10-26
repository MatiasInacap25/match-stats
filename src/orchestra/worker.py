"""How a Haiku worker is launched: claude CLI arguments and its per-worktree settings."""

import json
import shlex
from pathlib import Path

from orchestra.manifest import TaskSpec

WORKER_MODEL = "claude-haiku-5-5"
WORKER_PROMPT_FILE = Path(__file__).parent / "worker_prompt.md"
GUARDED_TOOLS = "Write|Edit|MultiEdit|NotebookEdit|Bash"


def worker_argv(task: TaskSpec, worktree: Path, settings_path: Path) -> list[str]:
    initial_prompt = (
        f"Read {task.prompt_file} and complete that task in this repository ({worktree}). "
        "When done, write .worker/RESULT.md and commit."
    )
    return [
        "--model", WORKER_MODEL,
        "--permission-mode", "bypassPermissions",
        "--settings", str(settings_path),
        "--strict-mcp-config",
        "--mcp-config", json.dumps({"mcpServers": {}}),
        "--disallowedTools", "Agent",
        "--append-system-prompt-file", str(WORKER_PROMPT_FILE),
        "-n", task.id,
        initial_prompt,
    ]


def write_worker_settings(worktree: Path, repo: Path) -> Path:
    command = (
        f"ORCHESTRA_WORKTREE_ROOT={shlex.quote(str(worktree))} "
        f"uv run --quiet --project {shlex.quote(str(repo))} python -m orchestra.guard"
        # If uv or Python itself fails, block instead of letting Claude Code treat it as "allow".
        " || exit 2"
    )
    settings = {
        "hooks": {
            "PreToolUse": [{"matcher": GUARDED_TOOLS, "hooks": [{"type": "command", "command": command}]}]
        }
    }
    path = worktree / ".worker" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))
    return path
