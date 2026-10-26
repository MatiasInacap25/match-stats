import json

from orchestra.cli import main


def test_cli_validate_rejects_bad_manifest(tmp_path, capsys):
    manifest = tmp_path / "bad.json"
    manifest.write_text(json.dumps({"name": "bad", "tasks": []}))

    code = main(["validate", str(manifest)])

    assert code == 1
    assert "no tasks" in capsys.readouterr().err


def test_cli_validate_accepts_good_manifest(tmp_path, capsys):
    (tmp_path / "a.md").write_text("x")
    manifest = tmp_path / "good.json"
    manifest.write_text(json.dumps({"name": "good", "tasks": [{"id": "task-a", "title": "A", "prompt_file": "a.md"}]}))

    code = main(["validate", str(manifest)])

    assert code == 0
    assert "task-a" in capsys.readouterr().out
