---
name: orchestrate-waves
description: Use when executing an implementation plan in this repo — split it into waves and run parallel Haiku workers in Herdr panes via `uv run orchestra`, then review and merge each result.
---

# Orchestrate waves

You are the orchestrator. Workers implement; you plan, launch, review, and merge.

## 1. Split the plan into waves

- A wave is a set of tasks that can run at the same time: they touch **disjoint files** and none consumes an interface another task in the same wave produces.
- Order waves by dependency. Put shared foundations (project config, shared types) in the first wave, ideally in one task.
- Prefer up to 4 tasks per wave (the concurrency cap). More is fine; they run in batches of 4.

## 2. Write the wave

For each task, write `waves/<wave>/<task-id>.md` containing:

- the plan task **verbatim** (files, interfaces, steps, expected outputs),
- the spec and plan paths,
- `Allowed files:` the exact paths the worker may create or change,
- `Test command:` the exact command that must pass.

Then write `waves/<wave>.json` (format in `waves/README.md`) with `base` set to the current feature branch.

## 3. Launch

```bash
uv run orchestra validate waves/<wave>.json
uv run orchestra run-wave waves/<wave>.json
```

Run `run-wave` in the background (it blocks until every worker settles, up to 45 min each). The user watches the Herdr tab `<wave> #<n>`. Read the JSON summary it prints.

## 4. Review each result

For each worker:

1. Read `status`, `pane_id` and `result_md` from the summary. Address workers by `pane_id`: workers that went through the trust dialog have no Herdr agent name.
2. `git -C <worktree> log --oneline <base>..HEAD` and `git diff <base>...<branch>`. Check the diff against the task: only allowed files, spec values respected, tests meaningful.
3. Run the task's test command inside the worktree.
4. **Correct** → from the main checkout: `git merge --no-ff <branch> -m "merge: <task-id>"`.
5. **Wrong** → one correction round: `herdr agent prompt <pane_id> "<exact fixes>" --wait --until idle --until done`, then review again. Still wrong → stop and report to the user with the evidence.
6. `blocked`/`not_started`/`error` → read the pane (`herdr pane read <pane_id> --source recent --lines 80`). `timeout` → the pane was closed; read `RESULT.md` and the branch. Then decide: one correction round, or report to the user.

## 5. Close the wave

1. Run the full test suite on the feature branch after all merges.
2. `uv run orchestra cleanup waves/<wave>.json` and close the wave's Herdr tab (`herdr tab close <tab-id>`).
3. Delete the merged `wave/<wave>/*` branches.
4. Save a short Engram note: wave name, merged tasks, rulings, problems.
5. Start the next wave.
