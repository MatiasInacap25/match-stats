from pathlib import Path

import pytest

from orchestra.herdr import AgentNotReady, AgentStartTimeout, Herdr, WorktreeExists
from orchestra.runner import CommandError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeRunner:
    def __init__(self, responses: list[str | CommandError] | None = None):
        self.calls: list[tuple[list[str], Path | None]] = []
        self.responses = list(responses or [])

    def run(self, argv: list[str], cwd: Path | None = None) -> str:
        self.calls.append((argv, cwd))
        response = self.responses.pop(0) if self.responses else ""
        if isinstance(response, CommandError):
            raise response
        return response


def test_create_worktree_path_and_branch(tmp_path):
    repo = tmp_path / "analisis"
    repo.mkdir()
    # `git rev-parse --verify` fails: the branch does not exist yet
    runner = FakeRunner([CommandError(["git"], 1, stdout="", stderr=""), ""])

    path = Herdr(runner).create_worktree(repo, "x", "wave/w1/x", "main")

    assert path == tmp_path / "analisis-worktrees" / "x"
    assert runner.calls[-1] == (["git", "worktree", "add", "-b", "wave/w1/x", str(path), "main"], repo)


def test_create_worktree_refuses_existing_path(tmp_path):
    repo = tmp_path / "analisis"
    repo.mkdir()
    (tmp_path / "analisis-worktrees" / "x").mkdir(parents=True)
    runner = FakeRunner()

    with pytest.raises(WorktreeExists, match="analisis-worktrees/x"):
        Herdr(runner).create_worktree(repo, "x", "wave/w1/x", "main")

    assert runner.calls == []


def test_create_worktree_refuses_existing_branch(tmp_path):
    repo = tmp_path / "analisis"
    repo.mkdir()
    # `git rev-parse --verify` succeeds (branch exists)
    runner = FakeRunner(["abc123\n"])
    herdr = Herdr(runner)

    with pytest.raises(WorktreeExists, match="wave/w1/x"):
        herdr.create_worktree(repo, "x", "wave/w1/x", "main")

    assert [argv for argv, _ in runner.calls] == [["git", "rev-parse", "--verify", "--quiet", "refs/heads/wave/w1/x"]]


def test_create_tab_and_split_parse_ids(tmp_path):
    runner = FakeRunner([fixture("tab_create.json"), fixture("pane_split.json")])
    herdr = Herdr(runner)

    tab_id, root_pane = herdr.create_tab("smoke #1", tmp_path)
    new_pane = herdr.split(root_pane, tmp_path, "right")

    assert (tab_id, root_pane, new_pane) == ("w3:t4", "w3:p1G", "w3:p1H")
    assert runner.calls[0][0] == ["herdr", "tab", "create", "--label", "smoke #1", "--cwd", str(tmp_path), "--no-focus"]
    assert runner.calls[1][0] == ["herdr", "pane", "split", "w3:p1G", "--direction", "right", "--cwd", str(tmp_path), "--no-focus"]


def test_start_agent_argv():
    runner = FakeRunner()

    Herdr(runner).start_agent("hello-a", "w3:p1H", ["--model", "claude-haiku-5-5", "go"])

    assert runner.calls[0][0] == [
        "herdr", "agent", "start", "hello-a", "--kind", "claude", "--pane", "w3:p1H", "--", "--model", "claude-haiku-5-5", "go",
    ]


def test_wait_agent_returns_status():
    runner = FakeRunner([fixture("agent_wait_ok.json")])

    status = Herdr(runner).wait_agent("hello-a", timeout_ms=1000)

    assert status == "working"
    assert runner.calls[0][0] == [
        "herdr", "agent", "wait", "hello-a", "--until", "idle", "--until", "done", "--until", "blocked", "--timeout", "1000",
    ]


def test_wait_started_waits_for_working():
    runner = FakeRunner([fixture("agent_wait_ok.json")])

    assert Herdr(runner).wait_started("hello-a", timeout_ms=5000) == "working"
    assert runner.calls[0][0] == ["herdr", "agent", "wait", "hello-a", "--until", "working", "--timeout", "5000"]


def test_wait_agent_timeout_maps_to_timeout():
    error = CommandError(["herdr"], 1, stdout="", stderr=fixture("agent_wait_timeout.json"))
    runner = FakeRunner([error])

    assert Herdr(runner).wait_agent("hello-a", timeout_ms=1) == "timeout"


def test_wait_agent_other_error_maps_to_error():
    error = CommandError(["herdr"], 1, stdout="", stderr=fixture("agent_wait_missing.json"))
    runner = FakeRunner([error])

    assert Herdr(runner).wait_agent("ghost", timeout_ms=1) == "error"


NOT_READY = '{"error":{"code":"agent_not_ready","message":"agent hello-a is blocked during startup"},"id":"cli:agent:start"}'
TRUST_SCREEN = """ Accessing workspace:
 {path}
 Quick safety check: Is this a project you created or one you trust? (Like your own code,
 ❯ No, exit
   Yes, I trust this folder
"""


def test_start_agent_not_ready_raises():
    runner = FakeRunner([CommandError(["herdr"], 1, stdout="", stderr=NOT_READY)])

    with pytest.raises(AgentNotReady):
        Herdr(runner).start_agent("hello-a", "w3:p1H", [])


def test_accept_trust_dialog_for_own_worktree(tmp_path):
    runner = FakeRunner([TRUST_SCREEN.format(path=tmp_path), ""])

    assert Herdr(runner).accept_trust_dialog("w3:p1H", tmp_path) is True
    assert runner.calls[0][0] == ["herdr", "pane", "read", "w3:p1H", "--source", "visible", "--lines", "40"]
    assert runner.calls[1][0] == ["herdr", "pane", "send-keys", "w3:p1H", "down", "enter"]


def test_refuses_trust_dialog_for_other_folder(tmp_path):
    runner = FakeRunner([TRUST_SCREEN.format(path="/home/someone/else"), ""])

    assert Herdr(runner).accept_trust_dialog("w3:p1H", tmp_path) is False
    assert len(runner.calls) == 1


def test_refuses_other_dialogs(tmp_path):
    runner = FakeRunner([f"{tmp_path}\n Bypass Permissions mode\n ❯ No, exit\n   Yes, I accept\n"])

    assert Herdr(runner).accept_trust_dialog("w3:p1H", tmp_path) is False
    assert len(runner.calls) == 1


START_TIMEOUT = '{"error":{"code":"timeout","message":"timed out waiting for agent startup"},"id":"cli:agent:start"}'


def test_start_agent_startup_timeout_raises_specific_error():
    runner = FakeRunner([CommandError(["herdr"], 1, stdout="", stderr=START_TIMEOUT)])

    with pytest.raises(AgentStartTimeout):
        Herdr(runner).start_agent("ingest", "w3:p1V", [])
