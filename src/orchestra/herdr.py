"""Thin adapter over the git and herdr CLIs. Herdr returns JSON on stdout, errors included."""

import json
import time
from pathlib import Path

from orchestra.runner import CommandError, Runner

WORKTREES_DIR_SUFFIX = "-worktrees"
SETTLED_STATUSES = ("idle", "done", "blocked")


# Claude Code asks to trust every new folder. orchestra only answers it for worktrees it created.
TRUST_PROMPT = "Is this a project you created or one you trust?"
TRUST_ACCEPT_KEYS = ("down", "enter")  # cursor starts on "No, exit"; the next option is "Yes, I trust this folder"


class WorktreeExists(RuntimeError):
    pass


class AgentNotReady(RuntimeError):
    """The agent process started but is stuck on a startup dialog."""


class AgentStartTimeout(RuntimeError):
    """Herdr gave up waiting to see the agent idle; it may already be working on its prompt."""


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
        try:
            self.runner.run(["herdr", "agent", "start", name, "--kind", "claude", "--pane", pane_id, "--", *args])
        except CommandError as exc:
            code = _error_code(exc.stderr) or _error_code(exc.stdout)
            if code == "agent_not_ready":
                raise AgentNotReady(str(exc)) from exc
            if code == "timeout":
                raise AgentStartTimeout(str(exc)) from exc
            raise

    def close_pane(self, pane_id: str) -> None:
        self.runner.run(["herdr", "pane", "close", pane_id])

    def read_pane(self, pane_id: str, lines: int = 40) -> str:
        return self.runner.run(["herdr", "pane", "read", pane_id, "--source", "visible", "--lines", str(lines)])

    def accept_trust_dialog(self, pane_id: str, worktree: Path) -> bool:
        """Answer "trust this folder" only when the pane shows that exact dialog for `worktree`."""
        screen = self.read_pane(pane_id)
        if TRUST_PROMPT not in screen or str(worktree) not in screen:
            return False
        self.runner.run(["herdr", "pane", "send-keys", pane_id, *TRUST_ACCEPT_KEYS])
        return True

    def wait_started(self, name: str, timeout_ms: int) -> str:
        """A freshly started agent is idle before it picks up its prompt; wait until it works.

        Right after a slow startup Herdr may not have registered the agent yet (agent_not_found),
        so an "error" is retried until the timeout instead of being final.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return "error"
            # "done" also proves it started: a fast worker can finish before we look.
            status = self._wait(name, ("working", "done"), remaining_ms)
            if status != "error":
                return status
            time.sleep(2)

    def wait_agent(self, name: str, timeout_ms: int) -> str:
        return self._wait(name, SETTLED_STATUSES, timeout_ms)

    def _wait(self, name: str, statuses: tuple[str, ...], timeout_ms: int) -> str:
        argv = ["herdr", "agent", "wait", name]
        for status in statuses:
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
