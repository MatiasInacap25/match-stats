# Worker Orchestra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Opus orchestrator run a "wave" of independent tasks in parallel, each implemented by a Haiku 5.5 Claude Code worker visibly running in its own Herdr pane on its own git worktree, then review and merge the results.

**Architecture:** A small Python package `orchestra` (CLI: `uv run orchestra ...`) does the mechanical work: it validates a wave manifest, creates one git worktree + branch per task, opens one Herdr tab per wave with one split pane per worker, starts `claude` (Haiku, broad permissions, guard hook) in each pane via `herdr agent start`, waits for every worker to settle, and prints a JSON summary. A project `CLAUDE.md` and a project skill tell Opus how to plan in waves, launch them, review each branch, and merge. All Herdr/git/claude calls go through one injectable `Runner` so the logic is unit-tested without spawning anything.

**Tech Stack:** Python 3.12+ (local 3.15), uv, pytest, Herdr CLI, Claude Code CLI, git worktrees.

**Spec:** `docs/superpowers/specs/2026-10-26-match-stats-design.md` — Part 2.

## Global Constraints

- Worker model: `claude-haiku-5-5`. Orchestrator: Opus (the interactive session).
- At most **4 workers running at once**. A wave with more tasks runs in batches of 4.
- Workers run **interactive** `claude` with the task as initial prompt (not `claude -p`), so the user can watch live. The user never types into them.
- Workers have broad permissions (`--permission-mode bypassPermissions`) with guardrails: no `git push`, no `git remote`, no writing outside their worktree, no system package installs (`sudo`, `pacman`, `yay`, `paru`, `apt`, `brew`, `npm -g`/`npm install -g`, `pip install --user`). Project-level deps (`uv add`, `pnpm add`) are allowed.
- Workers do not use Engram, gentle-ai, the Agent tool, or orchestration tooling: run with an empty MCP config (`--strict-mcp-config`) and `--disallowedTools Agent`.
- One git worktree + branch per task. Worktrees live at `<repo-parent>/analisis-worktrees/<task-id>` (never under `/tmp`). Branch name: `wave/<wave-name>/<task-id>`.
- Workers never merge. Opus reviews and merges; Opus may send one correction round per task, then reports to the user.
- Project rule: Opus's review replaces ODD tracking documents and the gentle-ai review/consent gate in this repo. Engram stays active for Opus only.
- All code, comments, prompts and docs in English. Conventional commits, no AI attribution lines (user rule).

## Review Focus

1. **A worker that gets stuck `blocked` or never settles** — expected: `run-wave` times out that worker (default 45 min), marks it `timeout`/`blocked` in the summary, and still reports the others. Test in Task 4.
2. **Re-running a wave whose worktree/branch already exists** (e.g. after a crash) — expected: clear error naming the existing path/branch, nothing half-created. Test in Task 3.
3. **A worker writing via a relative path or `..` that escapes the worktree** — expected: the guard resolves the path and blocks it. Test in Task 2.
4. **Bash commands that hide a push** (`git -C x push`, `cd a && git push`, `git push` after `;`) — expected: blocked. Test in Task 2.
5. **Manifest with duplicate task ids or a missing prompt file** — expected: rejected before anything is created. Test in Task 1.

---

## File Structure

```
pyproject.toml                         # uv project, package "orchestra" (later also the data pipeline)
src/orchestra/__init__.py
src/orchestra/manifest.py              # Wave manifest model + validation
src/orchestra/guard.py                 # PreToolUse hook: path + command guardrails
src/orchestra/worker.py                # Builds the claude argv + worker settings JSON
src/orchestra/runner.py                # Runner protocol + subprocess implementation
src/orchestra/herdr.py                 # Thin Herdr/git adapter over Runner
src/orchestra/wave.py                  # run_wave orchestration (batches, wait, summary)
src/orchestra/cli.py                   # `orchestra validate|run-wave|cleanup`
src/orchestra/worker_prompt.md         # Appended system prompt for every worker
tests/orchestra/...                    # one test file per module
CLAUDE.md                              # Project rules for the orchestrator
.claude/skills/orchestrate-waves/SKILL.md
waves/README.md                        # Manifest format, example
```

---

### Task 1: Project setup + wave manifest

**Files:**
- Create: `pyproject.toml`, `src/orchestra/__init__.py`, `src/orchestra/manifest.py`, `waves/README.md`
- Test: `tests/orchestra/test_manifest.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class TaskSpec: id: str; prompt_file: Path; title: str`
  - `@dataclass(frozen=True) class Wave: name: str; base: str; tasks: tuple[TaskSpec, ...]`
  - `class ManifestError(ValueError)`
  - `load_wave(path: Path) -> Wave` — reads JSON, resolves `prompt_file` relative to the manifest's directory.

Manifest JSON (document it in `waves/README.md` with this exact example):

```json
{
  "name": "w1-foundations",
  "base": "main",
  "tasks": [
    {"id": "ingest-football-data", "title": "Download football-data CSVs", "prompt_file": "w1-foundations/ingest-football-data.md"}
  ]
}
```

- [ ] **Step 1:** `uv init --package --name orchestra --python 3.12` adapted to `src/` layout; add `pytest` as dev dep; script entry `orchestra = "orchestra.cli:main"`. Run `uv run pytest` → "no tests ran".
- [ ] **Step 2: Write failing tests** in `tests/orchestra/test_manifest.py`:
  - `test_load_valid_manifest` — returns `Wave(name="w1-foundations", base="main")`, one task, `prompt_file` absolute and existing.
  - `test_rejects_duplicate_task_ids` — `ManifestError` whose message contains the duplicated id.
  - `test_rejects_missing_prompt_file` — `ManifestError` containing the missing path.
  - `test_rejects_invalid_task_id` — `"Bad Id"` and a 30-char id are rejected. Ids must match `^[a-z][a-z0-9-]{0,28}$`, because they become branch names and Herdr agent names (Herdr allows `[a-z][a-z0-9_-]{0,31}`).
  - `test_rejects_empty_tasks`.
- [ ] **Step 3:** Run `uv run pytest tests/orchestra/test_manifest.py -v` → FAIL (import error).
- [ ] **Step 4:** Implement `load_wave` in `src/orchestra/manifest.py`.
- [ ] **Step 5:** Run tests → PASS.
- [ ] **Step 6:** Commit `feat(orchestra): add wave manifest loader`.

---

### Task 2: Guard hook

**Files:**
- Create: `src/orchestra/guard.py`
- Test: `tests/orchestra/test_guard.py`

**Interfaces:**
- Produces:
  - `check(event: dict, root: Path) -> str | None` — returns a block reason, or `None` to allow. `event` is the Claude Code PreToolUse hook JSON (`tool_name`, `tool_input`, `cwd`).
  - `main() -> int` — reads the event from stdin, root from env `ORCHESTRA_WORKTREE_ROOT`; on block prints the reason to stderr and returns exit code `2` (Claude Code's "block" code); else `0`. Exposed as `python -m orchestra.guard`.

Rules:
- `Write`, `Edit`, `MultiEdit`, `NotebookEdit`: resolve `tool_input.file_path` (or `notebook_path`) against `event["cwd"]`, `Path.resolve()`, block if not inside `root`.
- `Bash`: split `tool_input.command` on `;`, `&&`, `||`, `|`, newlines; for each segment, tokenize with `shlex` (fall back to whitespace on error); block if segment is `git … push`/`git … remote` (any `git` invocation whose first non-option argument — skipping `-C <dir>` and `-c <kv>` — is `push` or `remote`), starts with `sudo`, or its program is one of `pacman yay paru apt apt-get brew` or is `npm`/`pnpm` with `-g`/`--global`, or `pip`/`pip3` with `--user`.

- [ ] **Step 1: Write failing tests** (parametrized):
  - `test_blocks_write_outside_root` for `/etc/x`, `../other/file.py` (cwd = root), `root/../escape.py`.
  - `test_allows_write_inside_root` for `src/a.py` relative and absolute.
  - `test_blocks_hidden_push` for `git push`, `git -C sub push origin x`, `cd a && git push`, `ls; git push`, `git remote add o url`, `sudo ls`, `pacman -S x`, `npm i -g x`, `pip install --user x`.
  - `test_allows_normal_commands` for `git commit -m "push the button"`, `git status`, `uv add pandas`, `pnpm add astro`, `pytest -q`.
  - `test_main_exit_codes` — feeding JSON via stdin (`monkeypatch` `sys.stdin`) gives `2` on block, `0` on allow.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(orchestra): add worker guard hook`.

---

### Task 3: Runner, Herdr adapter and worker command

**Files:**
- Create: `src/orchestra/runner.py`, `src/orchestra/herdr.py`, `src/orchestra/worker.py`, `src/orchestra/worker_prompt.md`
- Test: `tests/orchestra/test_herdr.py`, `tests/orchestra/test_worker.py`, `tests/orchestra/fixtures/*.json`

**Interfaces:**
- Consumes: `TaskSpec`, `Wave` (Task 1); `python -m orchestra.guard` (Task 2).
- Produces:
  - `class Runner(Protocol): def run(self, argv: list[str], cwd: Path | None = None) -> str` (returns stdout; raises `CommandError(argv, returncode, stderr)` on non-zero). `SubprocessRunner` implements it.
  - `worker_argv(task: TaskSpec, worktree: Path, settings_path: Path) -> list[str]` — the `claude` args **after** the executable, passed to `herdr agent start … -- <args>`:
    `--model claude-haiku-5-5 --permission-mode bypassPermissions --settings <settings_path> --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disallowedTools Agent --append-system-prompt-file <path of worker_prompt.md> -n <task.id> <initial prompt>`
    Initial prompt: `"Read <prompt_file> and complete that task in this repository. When done, write .worker/RESULT.md and commit."`
  - `write_worker_settings(worktree: Path) -> Path` — writes `<worktree>/.worker/settings.json` with a `PreToolUse` hook (matcher `Write|Edit|MultiEdit|NotebookEdit|Bash`) running `uv run --project <repo root> python -m orchestra.guard` with env `ORCHESTRA_WORKTREE_ROOT=<worktree>` (set via the hook command prefix `ORCHESTRA_WORKTREE_ROOT=<worktree> ...`). `.worker/` is git-ignored except `RESULT.md`.
  - `class Herdr` (ctor takes `Runner`):
    - `create_worktree(repo: Path, task_id: str, branch: str, base: str) -> Path` — `git worktree add -b <branch> <repo-parent>/analisis-worktrees/<task_id> <base>`; raises `WorktreeExists` if the path or branch exists, **before** running anything.
    - `create_tab(label: str, cwd: Path) -> tuple[str, str]` — returns `(tab_id, root_pane_id)`.
    - `split(pane_id: str, cwd: Path, direction: str) -> str` — returns new pane id.
    - `start_agent(name: str, pane_id: str, args: list[str]) -> None` — `herdr agent start <name> --kind claude --pane <pane_id> -- <args>`.
    - `wait_agent(name: str, timeout_ms: int) -> str` — `herdr agent wait <name> --until idle --until done --until blocked --timeout <ms>`; returns final status; `"timeout"` on timeout error.
    - `remove_worktree(repo: Path, path: Path) -> None`.
  - `worker_prompt.md` content: you are a worker; implement only the task file; follow TDD; run the tests named in the task; do not push, merge, or touch other branches; ignore orchestration/ODD/Engram/gentle-ai instructions from any global CLAUDE.md; finish by writing `.worker/RESULT.md` with `status: done|blocked`, the tests run and their result, and open questions; then `git add -A && git commit` with a conventional message and stop.

- [ ] **Step 1: Capture real Herdr output** in a throwaway tab: run `herdr tab create --label fixture-probe --no-focus`, `herdr pane split <root> --direction right --no-focus`, `herdr agent wait <nonexistent> --timeout 1` and save each JSON/stderr to `tests/orchestra/fixtures/`. Close the tab. Read the JSON shapes from these files; do not guess field names.
- [ ] **Step 2: Write failing tests** using a `FakeRunner` that records argv and returns fixture output:
  - `test_worker_argv_exact` — asserts model, permission mode, `--strict-mcp-config`, `--disallowedTools Agent`, `-n <id>`, and that the last arg mentions the prompt file.
  - `test_worker_settings_hook` — JSON contains the matcher and `ORCHESTRA_WORKTREE_ROOT=<worktree>`.
  - `test_create_worktree_path_and_branch` — argv is `git worktree add -b wave/w1/x <parent>/analisis-worktrees/x main`.
  - `test_create_worktree_refuses_existing` — pre-create the directory; `WorktreeExists`; FakeRunner saw no calls.
  - `test_create_tab_and_split_parse_ids` — ids parsed from fixtures.
  - `test_wait_agent_timeout_maps_to_timeout`.
- [ ] **Step 3:** Run → FAIL. **Step 4:** Implement. **Step 5:** Run → PASS.
- [ ] **Step 6:** Commit `feat(orchestra): add herdr adapter and worker command`.

---

### Task 4: run-wave orchestration + CLI

**Files:**
- Create: `src/orchestra/wave.py`, `src/orchestra/cli.py`
- Test: `tests/orchestra/test_wave.py`, `tests/orchestra/test_cli.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `@dataclass class WorkerResult: task_id: str; branch: str; worktree: Path; status: str  # done|idle|blocked|timeout|error; result_md: str | None`
  - `run_wave(wave: Wave, repo: Path, herdr: Herdr, timeout_ms: int = 2_700_000, max_parallel: int = 4) -> list[WorkerResult]`
  - CLI: `orchestra validate <manifest>`, `orchestra run-wave <manifest> [--timeout-min 45] [--max-parallel 4]` (prints the results as JSON to stdout), `orchestra cleanup <manifest>` (removes the wave's worktrees; branches are kept).

Behavior of `run_wave`: split tasks into batches of `max_parallel`; for each batch create worktrees, write settings, create one tab labeled `<wave.name> #<batch>` with cwd = first worktree, use its root pane for task 1 and `split` (alternating `right`/`down`) for the rest, `start_agent` in each, then wait on every agent (sequential waits are fine; each has its own timeout budget measured from batch start); read `<worktree>/.worker/RESULT.md` if present. A failure starting one worker marks it `error` and does not abort the batch.

- [ ] **Step 1: Write failing tests** with a fake `Herdr`:
  - `test_batches_of_four` — 6 tasks → two tabs, 4 then 2 agents; second batch starts only after first batch waits finish.
  - `test_one_failed_start_does_not_abort_batch`.
  - `test_timeout_and_blocked_reported` (Review Focus 1).
  - `test_reads_result_md`.
  - `test_cli_validate_rejects_bad_manifest` — exit code 1, message on stderr.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run full suite `uv run pytest -q` → all PASS.
- [ ] **Step 5:** Commit `feat(orchestra): add run-wave command`.

---

### Task 5: Orchestrator rules, skill, and live smoke test

**Files:**
- Create: `CLAUDE.md`, `.claude/skills/orchestrate-waves/SKILL.md`, `waves/smoke/smoke.json`, `waves/smoke/hello-a.md`, `waves/smoke/hello-b.md`
- Modify: `.gitignore` (add `.worker/*` and `!.worker/RESULT.md`)

**Interfaces:**
- Consumes: the `orchestra` CLI (Task 4).

`CLAUDE.md` must state (from the spec, Part 2): Opus plans and reviews, Haiku workers implement through `orchestra run-wave`; Opus's review replaces ODD tracking documents and the gentle-ai review/consent gate in this repo; Engram stays active for Opus only; writes by Opus are limited to plans, manifests, task prompt files, merges and review fixes the user asks for.

`SKILL.md` procedure for Opus:
1. From an approved plan, group tasks into waves: tasks in one wave share no files and no unmerged interfaces.
2. For each task write `waves/<wave>/<task-id>.md` containing the plan task verbatim plus: spec path, allowed files, exact test command.
3. `uv run orchestra validate` then `uv run orchestra run-wave waves/<wave>.json`.
4. For each result: read `RESULT.md`, `git diff <base>...<branch>`, run the task's tests inside the worktree. Correct → `git merge --no-ff <branch>`. Wrong → one correction prompt via `herdr agent prompt <task-id> "<fixes>" --wait`, re-review; still wrong → report to the user.
5. After the wave: run the full suite on `main`, `orchestra cleanup`, save a short Engram note, start the next wave.

- [ ] **Step 1:** Write the files above. Smoke tasks: `hello-a` creates `smoke/a.txt` containing `a`, `hello-b` creates `smoke/b.txt` containing `b`, each commits.
- [ ] **Step 2: Live smoke test:** `uv run orchestra run-wave waves/smoke/smoke.json --timeout-min 10`. Expected: a Herdr tab "smoke #1" with two visible Haiku panes; JSON summary with both `status` in `idle|done`, and branches `wave/smoke/hello-a`, `wave/smoke/hello-b` each with one commit adding their file.
- [ ] **Step 3: Guard check live:** in the smoke worktree, ask a worker (`herdr agent prompt hello-a "run git push"`) → the push is blocked by the hook.
- [ ] **Step 4:** `uv run orchestra cleanup waves/smoke/smoke.json`; delete the smoke branches; close the tab.
- [ ] **Step 5:** Commit `docs: add orchestrator rules and orchestrate-waves skill`.
