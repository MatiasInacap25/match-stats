# Task D: fixture-sources

Read the whole plan `docs/superpowers/plans/2026-10-27-calendar-sources-cups.md` and do **Task D** only. Another worker does the other task in parallel; stay inside your allowed files and never commit anything else.

The cached football-data season CSVs for the current season are in `/mnt/data/projects/analisis/data/raw/2627/` (read-only) if you need the real team names.

## Allowed files

- `src/matchstats/team_names.py`
- `src/matchstats/fixture_sources.py`
- `src/matchstats/build.py`
- `tests/matchstats/test_team_names.py`
- `tests/matchstats/test_fixture_sources.py`
- `tests/matchstats/test_build.py`
- `tests/matchstats/fixtures/fd_serie-a-2026_sample.json`
- `tests/matchstats/fixtures/fd_bundesliga-2026_sample.json`
- `tests/matchstats/fixtures/openligadb_dfb_2026_sample.json`
- `tests/matchstats/fixtures/teams_2627.json`
- `contract/data-contract.md`
- `contract/example/index.json`

## Test command (must pass before you finish)

`uv run pytest -q`
