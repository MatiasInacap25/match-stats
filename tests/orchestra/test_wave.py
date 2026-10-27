from pathlib import Path

from orchestra.herdr import AgentNotReady, AgentStartTimeout
from orchestra.manifest import TaskSpec, Wave
from orchestra.wave import run_wave


class FakeHerdr:
    """Records the orchestration sequence; worktrees are real directories under tmp_path."""

    def __init__(
        self,
        root: Path,
        statuses: dict[str, str] | None = None,
        failing_starts: set[str] = frozenset(),
        not_ready: set[str] = frozenset(),
        slow_start: set[str] = frozenset(),
        trust_dialog: bool = True,
    ):
        self.root = root
        self.not_ready = not_ready
        self.slow_start = slow_start
        self.trust_dialog = trust_dialog
        self.pane_names: dict[str, str] = {}
        self.never_working: set[str] = set()
        self.events: list[tuple] = []
        self.statuses = statuses or {}
        self.failing_starts = failing_starts
        self._panes = 0

    def create_worktree(self, repo, task_id, branch, base):
        path = self.root / "worktrees" / task_id
        path.mkdir(parents=True)
        self.events.append(("worktree", task_id, branch, base))
        return path

    def create_tab(self, label, cwd):
        self.events.append(("tab", label))
        return f"t-{label}", self._new_pane()

    def split(self, pane_id, cwd, direction):
        self.events.append(("split", pane_id, direction))
        return self._new_pane()

    def start_agent(self, name, pane_id, args):
        if name in self.failing_starts:
            raise RuntimeError(f"cannot start {name}")
        self.pane_names[pane_id] = name
        if name in self.not_ready:
            raise AgentNotReady(f"agent {name} is blocked during startup")
        if name in self.slow_start:
            raise AgentStartTimeout(f"timed out waiting for {name} startup")
        self.events.append(("start", name, pane_id))

    def accept_trust_dialog(self, pane_id, worktree):
        self.events.append(("trust", self.pane_names[pane_id], worktree.name))
        return self.trust_dialog

    def wait_started(self, target, timeout_ms):
        name = self.pane_names.get(target, target)
        self.events.append(("started", name))
        return "timeout" if name in self.never_working else "working"

    def close_pane(self, pane_id):
        self.events.append(("close", self.pane_names.get(pane_id, pane_id)))

    def wait_agent(self, target, timeout_ms):
        name = self.pane_names.get(target, target)
        self.events.append(("wait", name))
        return self.statuses.get(name, "idle")

    def _new_pane(self):
        self._panes += 1
        return f"p{self._panes}"


def make_wave(tmp_path: Path, count: int) -> Wave:
    prompt = tmp_path / "p.md"
    prompt.write_text("x")
    tasks = tuple(TaskSpec(id=f"task-{i}", prompt_file=prompt, title=f"T{i}") for i in range(count))
    return Wave(name="w1", base="main", tasks=tasks)


def test_batches_of_four(tmp_path):
    herdr = FakeHerdr(tmp_path)

    results = run_wave(make_wave(tmp_path, 6), tmp_path / "repo", herdr)

    assert [e for e in herdr.events if e[0] == "tab"] == [("tab", "w1 #1"), ("tab", "w1 #2")]
    kinds = [e[0] + ":" + e[1] for e in herdr.events if e[0] in {"start", "wait", "tab"}]
    second_tab = kinds.index("tab:w1 #2")
    assert sum(k.startswith("start") for k in kinds[:second_tab]) == 4
    assert sum(k.startswith("wait") for k in kinds[:second_tab]) == 4  # batch 1 finished before batch 2 starts
    assert sum(k.startswith("start") for k in kinds[second_tab:]) == 2
    assert [r.task_id for r in results] == [f"task-{i}" for i in range(6)]
    assert results[0].branch == "wave/w1/task-0"


def test_one_failed_start_does_not_abort_batch(tmp_path):
    herdr = FakeHerdr(tmp_path, failing_starts={"task-1"})

    results = {r.task_id: r for r in run_wave(make_wave(tmp_path, 3), tmp_path / "repo", herdr)}

    assert results["task-1"].status == "error"
    assert results["task-0"].status == "idle"
    assert results["task-2"].status == "idle"
    assert ("wait", "task-1") not in herdr.events


def test_timeout_and_blocked_reported(tmp_path):
    herdr = FakeHerdr(tmp_path, statuses={"task-0": "timeout", "task-1": "blocked"})

    results = {r.task_id: r.status for r in run_wave(make_wave(tmp_path, 3), tmp_path / "repo", herdr)}

    assert results == {"task-0": "timeout", "task-1": "blocked", "task-2": "idle"}


def test_reads_result_md(tmp_path):
    herdr = FakeHerdr(tmp_path)
    wave = make_wave(tmp_path, 1)
    original = herdr.wait_agent

    def wait_and_write(target, timeout_ms):
        name = herdr.pane_names[target]
        result = tmp_path / "worktrees" / name / ".worker" / "RESULT.md"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text("status: done\n")
        return original(target, timeout_ms)

    herdr.wait_agent = wait_and_write

    [result] = run_wave(wave, tmp_path / "repo", herdr)

    assert result.result_md == "status: done\n"


def test_splits_alternate_directions(tmp_path):
    herdr = FakeHerdr(tmp_path)

    run_wave(make_wave(tmp_path, 4), tmp_path / "repo", herdr)

    assert [e[2] for e in herdr.events if e[0] == "split"] == ["right", "down", "right"]


def test_writes_worker_settings_in_each_worktree(tmp_path):
    herdr = FakeHerdr(tmp_path)

    run_wave(make_wave(tmp_path, 2), tmp_path / "repo", herdr)

    for i in range(2):
        assert (tmp_path / "worktrees" / f"task-{i}" / ".worker" / "settings.json").is_file()


def test_accepts_trust_dialog_for_own_worktree(tmp_path):
    herdr = FakeHerdr(tmp_path, not_ready={"task-0"})

    [result] = run_wave(make_wave(tmp_path, 1), tmp_path / "repo", herdr)

    assert ("trust", "task-0", "task-0") in herdr.events
    assert ("wait", "task-0") in herdr.events
    assert result.status == "idle"


def test_unknown_startup_dialog_is_an_error(tmp_path):
    herdr = FakeHerdr(tmp_path, not_ready={"task-0"}, trust_dialog=False)

    [result] = run_wave(make_wave(tmp_path, 1), tmp_path / "repo", herdr)

    assert result.status == "error"
    assert "blocked during startup" in result.error
    assert ("wait", "task-0") not in herdr.events


def test_worker_that_never_starts_is_not_success(tmp_path):
    herdr = FakeHerdr(tmp_path)
    herdr.never_working = {"task-0"}

    [result] = run_wave(make_wave(tmp_path, 1), tmp_path / "repo", herdr)

    assert result.status == "not_started"
    assert ("wait", "task-0") not in herdr.events


def test_timed_out_worker_is_stopped_before_next_batch(tmp_path):
    herdr = FakeHerdr(tmp_path, statuses={"task-0": "timeout"})

    run_wave(make_wave(tmp_path, 5), tmp_path / "repo", herdr)

    kinds = [(e[0], e[1]) for e in herdr.events]
    assert kinds.index(("close", "task-0")) < kinds.index(("tab", "w1 #2"))


def test_startup_timeout_still_tracks_the_worker(tmp_path):
    herdr = FakeHerdr(tmp_path, slow_start={"task-0"})

    [result] = run_wave(make_wave(tmp_path, 1), tmp_path / "repo", herdr)

    assert ("wait", "task-0") in herdr.events
    assert result.status == "idle"
