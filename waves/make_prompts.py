"""Generate a wave's task prompts and manifest from the site plan.

Usage: uv run python waves/make_prompts.py <wave-spec.json>

The wave spec lists, per task: plan task number, id, title, allowed files, test command.
Each prompt embeds the plan task verbatim plus global constraints, review focus and notes.
"""

import json
import re
import sys
from pathlib import Path

PLAN = Path("docs/superpowers/plans/2026-10-26-match-stats-site.md")


def plan_sections() -> tuple[dict[int, str], str, str]:
    plan = PLAN.read_text()
    tasks = {}
    for section in re.split(r"\n(?=### Task \d+:)", plan):
        match = re.match(r"### Task (\d+)", section)
        if match:
            tasks[int(match.group(1))] = section.split("\n### Wave 4")[0].split("\n---")[0].strip()
    constraints = plan.split("## Global Constraints")[1].split("## Review Focus")[0].strip()
    focus = plan.split("## Review Focus")[1].split("---")[0].strip()
    return tasks, constraints, focus


def main(spec_path: str) -> None:
    spec = json.loads(Path(spec_path).read_text())
    tasks, constraints, focus = plan_sections()
    name = spec["name"]
    directory = Path("waves") / name
    directory.mkdir(parents=True, exist_ok=True)
    notes = "\n".join(f"- {n}" for n in spec.get("notes", [])) or "- none"
    manifest = {"name": name, "base": spec["base"], "tasks": []}
    for task in spec["tasks"]:
        allowed = "\n".join(f"- `{f}`" for f in task["files"])
        body = f"""# Task {task['plan_task']}: {task['id']}

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `{PLAN}`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

{allowed}

## Test command (must pass before you finish)

`{task['test']}`

## Notes from earlier waves (binding)

{notes}

## Global constraints (from the plan)

{constraints}

## Review focus items (from the plan; cover the ones your task owns)

{focus}

## Your task (verbatim from the plan)

{tasks[task['plan_task']]}
"""
        (directory / f"{task['id']}.md").write_text(body)
        manifest["tasks"].append({"id": task["id"], "title": task["title"], "prompt_file": f"{name}/{task['id']}.md"})
    (Path("waves") / f"{name}.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
