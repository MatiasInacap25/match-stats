# Task A: data-upcoming

Read the whole plan `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` and do **Task A** only. Other workers do the other tasks in parallel; stay inside your allowed files and never commit anything else.

Reference files outside this worktree (read-only, absolute paths):
- Approved visual mockup: `/mnt/data/projects/analisis/.superpowers/brainstorm/67728-1793055210/content/ui-direction.html`
- Design rules (binding for UI edits): `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`, `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/operate.md`
- Pre-delivery checklist: `/mnt/data/projects/analisis/.claude/skills/ui-ux-pro-max/references/pro-rules.md`
- Never run anything under `/mnt/data/projects/analisis/.claude/skills/impeccable/scripts/`.

Data contract: `contract/data-contract.md` and `contract/example/`.

## Allowed files

- `src/matchstats/build.py`
- `tests/matchstats/test_build.py`
- `contract/data-contract.md`
- `contract/example/index.json`

## Test command (must pass before you finish)

`uv run pytest -q`
