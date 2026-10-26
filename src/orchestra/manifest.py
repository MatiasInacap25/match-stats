"""Wave manifest: the list of independent tasks Opus hands to parallel workers."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Task ids become git branch names and Herdr agent names ([a-z][a-z0-9_-]{0,31}).
TASK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,28}$")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class TaskSpec:
    id: str
    prompt_file: Path
    title: str


@dataclass(frozen=True)
class Wave:
    name: str
    base: str
    tasks: tuple[TaskSpec, ...]


def load_wave(path: Path) -> Wave:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc

    raw_tasks = data.get("tasks") or []
    if not raw_tasks:
        raise ManifestError(f"manifest {path} has no tasks")

    tasks: list[TaskSpec] = []
    seen: set[str] = set()
    for raw in raw_tasks:
        task_id = raw.get("id", "")
        if not TASK_ID_PATTERN.match(task_id):
            raise ManifestError(f"invalid task id {task_id!r}: must match {TASK_ID_PATTERN.pattern}")
        if task_id in seen:
            raise ManifestError(f"duplicate task id {task_id!r}")
        seen.add(task_id)

        rel = raw.get("prompt_file", "")
        prompt_file = (path.parent / rel).resolve()
        if not rel or not prompt_file.is_file():
            raise ManifestError(f"prompt file not found for {task_id!r}: {rel}")

        tasks.append(TaskSpec(id=task_id, prompt_file=prompt_file, title=raw.get("title", task_id)))

    return Wave(name=data.get("name") or path.stem, base=data.get("base") or "main", tasks=tuple(tasks))
