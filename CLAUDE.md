# Project rules: analisis

These rules override the global `~/.claude/CLAUDE.md` for this repository.

## Roles

- **The interactive session (Opus) is the orchestrator.** It plans, splits plans into waves, launches workers, reviews their results, and merges.
- **Workers are Haiku 5.5 (`claude-haiku-5-5`) Claude Code sessions**, one per task, each in its own Herdr pane and git worktree, launched only through `uv run orchestra run-wave`. Workers write the product code.
- Opus writes plans, wave manifests, task prompt files, merges, and review fixes the user asks for. It does not implement plan tasks itself unless the user asks.
- To run a wave, use the `orchestrate-waves` skill (`.claude/skills/orchestrate-waves/SKILL.md`).

## Overrides of global rules

- **Opus's review of each worker's result replaces** ODD feature-document tracking and the gentle-ai review/consent gate in this repo. Do not run `gentle-ai review` here.
- Delegation limits from the global rules do not apply to workers launched by `orchestra`.
- **Engram stays active for Opus only**: save decisions and a short note after each wave.
- Workers never use Engram, gentle-ai, the Agent tool, or orchestration tooling (enforced by `orchestra`: empty MCP config, `--disallowedTools Agent`, guard hook).

## Guardrails

- At most 4 workers at once.
- The guard hook (`orchestra.guard`, fails closed) blocks workers from: `git push`/`git remote`; rewriting shared refs (`git update-ref`, `symbolic-ref`, `worktree`, `branch -f/-d/-D/-m`); writing outside their worktree **with the file tools** (Write/Edit/MultiEdit/NotebookEdit); and installing system software.
- Not covered: shell redirections or `cp`/`rm`/`tee` targeting paths outside the worktree. Check during review that a worker's diff and the main checkout are untouched outside its worktree.
- Only Opus merges, and only into the local feature branch. Pushing and opening PRs remain the user's decision. The nightly data job's automatic commit (product spec) is the only automated push.

## Docs

- Design: `docs/superpowers/specs/2026-10-26-match-stats-design.md`
- Plans: `docs/superpowers/plans/`
- Wave manifests: `waves/` (format in `waves/README.md`)
