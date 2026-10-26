import json
from pathlib import Path

import pytest

from orchestra.manifest import ManifestError, load_wave


def write_manifest(tmp_path: Path, tasks: list[dict], name: str = "w1-foundations") -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"name": name, "base": "main", "tasks": tasks}))
    return path


def write_prompt(tmp_path: Path, rel: str) -> None:
    prompt = tmp_path / rel
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text("# task\n")


def test_load_valid_manifest(tmp_path):
    write_prompt(tmp_path, "w1-foundations/ingest-football-data.md")
    path = write_manifest(
        tmp_path,
        [{"id": "ingest-football-data", "title": "Download CSVs", "prompt_file": "w1-foundations/ingest-football-data.md"}],
    )

    wave = load_wave(path)

    assert wave.name == "w1-foundations"
    assert wave.base == "main"
    assert len(wave.tasks) == 1
    task = wave.tasks[0]
    assert task.id == "ingest-football-data"
    assert task.title == "Download CSVs"
    assert task.prompt_file.is_absolute()
    assert task.prompt_file.exists()


def test_rejects_duplicate_task_ids(tmp_path):
    write_prompt(tmp_path, "a.md")
    path = write_manifest(
        tmp_path,
        [
            {"id": "dup-task", "title": "x", "prompt_file": "a.md"},
            {"id": "dup-task", "title": "y", "prompt_file": "a.md"},
        ],
    )

    with pytest.raises(ManifestError, match="dup-task"):
        load_wave(path)


def test_rejects_missing_prompt_file(tmp_path):
    path = write_manifest(tmp_path, [{"id": "task-a", "title": "x", "prompt_file": "missing/prompt.md"}])

    with pytest.raises(ManifestError, match="missing/prompt.md"):
        load_wave(path)


@pytest.mark.parametrize("bad_id", ["Bad Id", "a" * 30, "1starts-with-digit", "under_score"])
def test_rejects_invalid_task_id(tmp_path, bad_id):
    write_prompt(tmp_path, "a.md")
    path = write_manifest(tmp_path, [{"id": bad_id, "title": "x", "prompt_file": "a.md"}])

    with pytest.raises(ManifestError, match="invalid task id"):
        load_wave(path)


def test_rejects_empty_tasks(tmp_path):
    path = write_manifest(tmp_path, [])

    with pytest.raises(ManifestError, match="no tasks"):
        load_wave(path)
