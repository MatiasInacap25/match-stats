import json
from pathlib import Path

from orchestra.manifest import TaskSpec
from orchestra.worker import WORKER_MODEL, WORKER_PROMPT_FILE, worker_argv, write_worker_settings


def make_task(tmp_path: Path) -> TaskSpec:
    prompt = tmp_path / "waves" / "smoke" / "hello-a.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("# hello\n")
    return TaskSpec(id="hello-a", prompt_file=prompt, title="Hello A")


def test_worker_argv_exact(tmp_path):
    task = make_task(tmp_path)
    settings = tmp_path / "settings.json"

    argv = worker_argv(task, tmp_path / "wt", settings)

    assert WORKER_MODEL == "claude-haiku-5-5"
    assert argv[argv.index("--model") + 1] == "claude-haiku-5-5"
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    assert argv[argv.index("--settings") + 1] == str(settings)
    assert "--strict-mcp-config" in argv
    assert json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert argv[argv.index("--disallowedTools") + 1] == "Agent"
    assert argv[argv.index("--append-system-prompt-file") + 1] == str(WORKER_PROMPT_FILE)
    assert argv[argv.index("-n") + 1] == "hello-a"
    assert str(task.prompt_file) in argv[-1]
    assert ".worker/RESULT.md" in argv[-1]


def test_worker_prompt_file_exists():
    assert WORKER_PROMPT_FILE.is_file()
    text = WORKER_PROMPT_FILE.read_text()
    assert "RESULT.md" in text
    assert "push" in text
    assert "never force-add or commit it" in text


def test_result_file_is_git_ignored():
    gitignore = (Path(__file__).parents[2] / ".gitignore").read_text().splitlines()
    assert ".worker/" in gitignore


def test_worker_settings_hook(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    repo = tmp_path / "repo"

    path = write_worker_settings(worktree, repo)

    assert path == worktree / ".worker" / "settings.json"
    settings = json.loads(path.read_text())
    entry = settings["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "Write|Edit|MultiEdit|NotebookEdit|Bash"
    command = entry["hooks"][0]["command"]
    assert f"ORCHESTRA_WORKTREE_ROOT={worktree}" in command
    assert f"--project {repo}" in command
    assert "python -m orchestra.guard" in command
