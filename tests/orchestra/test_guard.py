import io
import json

import pytest

from orchestra import guard


def edit_event(file_path: str, cwd: str, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": file_path}, "cwd": cwd}


def bash_event(command: str, cwd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


@pytest.fixture
def root(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    return worktree


@pytest.mark.parametrize("target", ["/etc/x", "../other/file.py", "{root}/../escape.py"])
def test_blocks_write_outside_root(root, target):
    event = edit_event(target.format(root=root), cwd=str(root))

    assert guard.check(event, root) is not None


@pytest.mark.parametrize("target", ["src/a.py", "{root}/src/a.py"])
@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_allows_write_inside_root(root, target, tool):
    event = edit_event(target.format(root=root), cwd=str(root), tool=tool)

    assert guard.check(event, root) is None


def test_blocks_notebook_outside_root(root):
    event = {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/tmp/n.ipynb"}, "cwd": str(root)}

    assert guard.check(event, root) is not None


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git -C sub push origin x",
        "git -c user.name=x push",
        "cd a && git push",
        "ls; git push",
        "echo ok\ngit push --force",
        "git remote add o url",
        "sudo ls",
        "pacman -S x",
        "yay -S x",
        "apt-get install x",
        "brew install x",
        "npm i -g x",
        "pnpm add --global x",
        "pip install --user x",
    ],
)
def test_blocks_hidden_push_and_system_installs(root, command):
    assert guard.check(bash_event(command, str(root)), root) is not None


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "push the button"',
        "git status",
        "git log --oneline | head",
        "uv add pandas",
        "pnpm add astro",
        "pytest -q",
    ],
)
def test_allows_normal_commands(root, command):
    assert guard.check(bash_event(command, str(root)), root) is None


def test_main_exit_codes(root, monkeypatch, capsys):
    monkeypatch.setenv("ORCHESTRA_WORKTREE_ROOT", str(root))

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(bash_event("git push", str(root)))))
    assert guard.main() == 2
    assert "push" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(bash_event("git status", str(root)))))
    assert guard.main() == 0
