"""Plain-text checks for the Vercel config and README (the GitHub Actions job was removed).

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


def test_no_github_actions_workflow():
    assert not WORKFLOW.exists()


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
    assert "Root Directory" in text or "root directory" in text
    assert "HY + 2 × HR" in text
