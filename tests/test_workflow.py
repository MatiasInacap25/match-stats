"""Plain-text checks for the nightly data job, Vercel config and README.

No YAML library: the workflow is asserted as text so the test has no extra
dependency and fails loudly on any drift from the plan.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "nightly.yml"
VERCEL = ROOT / "site" / "vercel.json"
README = ROOT / "README.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_file_exists():
    assert WORKFLOW.is_file()


def test_nightly_cron_string():
    assert 'cron: "0 2 * * *"' in read(WORKFLOW)


def test_workflow_dispatch_trigger():
    text = read(WORKFLOW)
    assert "workflow_dispatch:" in text
    assert "schedule:" in text


def test_contents_write_permission():
    text = read(WORKFLOW)
    assert "permissions:" in text
    assert "contents: write" in text


def test_checkout_uv_and_cache_steps():
    text = read(WORKFLOW)
    assert "actions/checkout@v4" in text
    assert "astral-sh/setup-uv@v6" in text
    assert "actions/cache@v4" in text
    assert "path: data/raw" in text
    assert "key: raw-${{ github.run_id }}" in text
    assert "restore-keys: raw-" in text


def test_uv_sync_is_frozen():
    assert "uv sync --frozen" in read(WORKFLOW)


def test_exact_build_command():
    assert "uv run matchstats build --out site/public/data --cache data/raw" in read(
        WORKFLOW
    )


def test_commit_message():
    assert 'git commit -m "chore(data): nightly update"' in read(WORKFLOW)


def test_bot_identity_configured():
    assert "github-actions[bot]" in read(WORKFLOW)


def test_push_only_behind_porcelain_check():
    text = read(WORKFLOW)
    guard = 'if [ -n "$(git status --porcelain site/public/data)" ]; then'
    assert guard in text
    guard_at = text.index(guard)
    push_at = text.index("git push")
    commit_at = text.index('git commit -m "chore(data): nightly update"')
    block_end = text.index("\n          fi", guard_at)
    assert guard_at < commit_at < push_at < block_end
    # The build step must come before the guard: a failed build stops the job.
    assert text.index("uv run matchstats build") < guard_at


def test_vercel_config_parses_with_three_keys():
    data = json.loads(read(VERCEL))
    assert data == {
        "buildCommand": "npm run build",
        "outputDirectory": "dist",
        "installCommand": "npm ci",
    }


def test_readme_covers_local_use_and_user_steps():
    text = read(README)
    assert "uv run matchstats build --out site/public/data --cache data/raw" in text
    assert "npm run dev" in text
    assert "npm run dev:example" in text
    assert "uv run python -m matchstats.backtest --league E0 --season 2526 --cache data/raw" in text
    assert "waves/README.md" in text
    assert "Read and write permissions" in text
    assert "Root Directory" in text or "root directory" in text
    assert "HY + 2 × HR" in text
