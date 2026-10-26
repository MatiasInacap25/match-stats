# Waves

A wave is a set of independent tasks that run in parallel, one Haiku worker per task, each in its own Herdr pane and git worktree. Tasks in the same wave must not share files or depend on each other's unmerged code.

## Manifest format

`waves/<wave-name>.json`:

```json
{
  "name": "w1-foundations",
  "base": "main",
  "tasks": [
    {"id": "ingest-football-data", "title": "Download football-data CSVs", "prompt_file": "w1-foundations/ingest-football-data.md"}
  ]
}
```

- `id`: lowercase, digits and dashes, starts with a letter, at most 29 characters. It becomes the branch `wave/<name>/<id>` and the Herdr agent name.
- `prompt_file`: path relative to the manifest. It holds the full task for the worker.
- `base`: the ref every worktree branches from.

## Commands

```bash
uv run orchestra validate waves/<wave>.json
uv run orchestra run-wave waves/<wave>.json [--timeout-min 45] [--max-parallel 4]
uv run orchestra cleanup waves/<wave>.json
```
