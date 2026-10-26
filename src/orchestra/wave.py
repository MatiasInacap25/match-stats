"""Run one wave: batches of parallel workers, one Herdr tab per batch, one pane per worker."""

import time
from dataclasses import dataclass
from pathlib import Path

from orchestra.manifest import TaskSpec, Wave
from orchestra.worker import worker_argv, write_worker_settings

DEFAULT_TIMEOUT_MS = 45 * 60 * 1000
START_TIMEOUT_MS = 2 * 60 * 1000
SPLIT_DIRECTIONS = ("right", "down")


@dataclass
class WorkerResult:
    task_id: str
    branch: str
    worktree: Path | None
    status: str  # done | idle | blocked | timeout | error
    result_md: str | None = None
    error: str | None = None


def branch_name(wave: Wave, task: TaskSpec) -> str:
    return f"wave/{wave.name}/{task.id}"


def run_wave(
    wave: Wave, repo: Path, herdr, timeout_ms: int = DEFAULT_TIMEOUT_MS, max_parallel: int = 4
) -> list[WorkerResult]:
    results: list[WorkerResult] = []
    tasks = list(wave.tasks)
    for batch_number, start in enumerate(range(0, len(tasks), max_parallel), start=1):
        batch = tasks[start : start + max_parallel]
        results += _run_batch(wave, batch, batch_number, repo, herdr, timeout_ms)
    return results


def _run_batch(wave, batch, batch_number, repo, herdr, timeout_ms) -> list[WorkerResult]:
    results: list[WorkerResult] = []
    for task in batch:
        branch = branch_name(wave, task)
        try:
            worktree = herdr.create_worktree(repo, task.id, branch, wave.base)
            write_worker_settings(worktree, repo)
        except Exception as exc:  # one broken task must not sink the batch
            results.append(WorkerResult(task.id, branch, None, "error", error=str(exc)))
            continue
        results.append(WorkerResult(task.id, branch, worktree, "pending"))

    pending = [r for r in results if r.status == "pending"]
    if not pending:
        return results

    _, pane = herdr.create_tab(f"{wave.name} #{batch_number}", pending[0].worktree)
    tasks_by_id = {t.id: t for t in batch}
    for index, result in enumerate(pending):
        if index > 0:
            pane = herdr.split(pane, result.worktree, SPLIT_DIRECTIONS[(index - 1) % 2])
        task = tasks_by_id[result.task_id]
        settings = result.worktree / ".worker" / "settings.json"
        try:
            herdr.start_agent(task.id, pane, worker_argv(task, result.worktree, settings))
        except Exception as exc:
            result.status, result.error = "error", str(exc)

    started_at = time.monotonic()
    for result in pending:
        if result.status == "error":
            continue
        herdr.wait_started(result.task_id, START_TIMEOUT_MS)
        remaining = max(1, timeout_ms - int((time.monotonic() - started_at) * 1000))
        result.status = herdr.wait_agent(result.task_id, remaining)
        result_file = result.worktree / ".worker" / "RESULT.md"
        if result_file.is_file():
            result.result_md = result_file.read_text()
    return results
