"""Thin adapter over the git and herdr CLIs. Herdr returns JSON on stdout, errors included."""

import json
from pathlib import Path

from orchestra.runner import CommandError, Runner

WORKTREES_DIR_SUFFIX = "-worktrees"
SETTLED_STATUSES = ("idle", "done", "blocked")


class WorktreeExists(RuntimeError):
    pass


def worktree_path(repo: Path, task_id: str) -> Path:
    return repo.parent / f"{repo.name}{WORKTREES_DIR_SUFFIX}" / task_id


class Herdr:
    def __init__(self, runner: Runner):
        self.runner = runner

    def create_worktree(self, repo: Path, task_id: str, branch: str, base: str) -> Path:
        path = worktree_path(repo, task_id)
        if path.exists():
            raise WorktreeExists(f"worktree path already exists: {path}")
        if self._branch_exists(repo, branch):
            raise WorktreeExists(f"branch already exists: {branch}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(["git", "worktree", "add", "-b", branch, str(path), base], cwd=repo)
        return path

    def remove_worktree(self, repo: Path, path: Path) -> None:
        self.runner.run(["git", "worktree", "remove", "--force", str(path)], cwd=repo)

    def create_tab(self, label: str, cwd: Path) -> tuple[str, str]:
        out = self.runner.run(["herdr", "tab", "create", "--label", label, "--cwd", str(cwd), "--no-focus"])
        result = json.loads(out)["result"]
        return result["tab"]["tab_id"], result["root_pane"]["pane_id"]

    def split(self, pane_id: str, cwd: Path, direction: str) -> str:
        out = self.runner.run(
            ["herdr", "pane", "split", pane_id, "--direction", direction, "--cwd", str(cwd), "--no-focus"]
        )
        return json.loads(out)["result"]["pane"]["pane_id"]

    def start_agent(self, name: str, pane_id: str, args: list[str]) -> None:
        self.runner.run(["herdr", "agent", "start", name, "--kind", "claude", "--pane", pane_id, "--", *args])

    def wait_agent(self, name: str, timeout_ms: int) -> str:
        argv = ["herdr", "agent", "wait", name]
        for status in SETTLED_STATUSES:
            argv += ["--until", status]
        argv += ["--timeout", str(timeout_ms)]
        try:
            out = self.runner.run(argv)
        except CommandError as exc:
            # Herdr prints its error envelope on stderr.
            code = _error_code(exc.stderr) or _error_code(exc.stdout)
            return "timeout" if code == "timeout" else "error"
        return json.loads(out)["result"]["agent"]["agent_status"]

    def _branch_exists(self, repo: Path, branch: str) -> bool:
        try:
            self.runner.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
        except CommandError:
            return False
        return True


def _error_code(stdout: str) -> str | None:
    try:
        return json.loads(stdout)["error"]["code"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
