# Task 7: build-cli

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `src/matchstats/build.py`
- `src/matchstats/cli.py`
- `pyproject.toml`
- `uv.lock`
- `tests/matchstats/test_build.py`

## Test command (must pass before you finish)

`uv run pytest -q`

## Notes from earlier waves (binding)

- Match.season holds the season code (e.g. "2627"); use leagues.season_label() for the JSON 'season' field ("2026/27").
- Existing signatures: fit_goals_model(matches, ref_date, xi=0.002, l2=0.1) -> dict (raises ValueError on empty input); fit_stat_model(matches, stat, current_season, shrink=5.0) -> dict (raises ValueError on empty input or unknown stat); STAT_FIELDS in stat_model; league_table(matches); season_stats(matches, team, table); last_matches(matches, team, n=6); pair_key(a, b); head_to_head(matches, a, b); load_matches(divs, seasons, cache_dir, current_season); download(url, cache_file, refresh) -> str | None; parse_fixtures_csv(text); FIXTURES_URL; season_code(d); season_label(code); recent_seasons(current, n); TOP_LEAGUES; SECOND_DIVISION.
- fit_stat_model only returns teams that appear in the matches it gets; season_stats returns position/points None for a team missing from the table. The build must pass the right matches so every current-season team is present; validate_output catches gaps.
- Contract: when a season side has matches == 0, its per-match averages and *_pct are null.
- site/public/data/ is written by the build and committed only by the nightly job. Tests must write to tmp_path, never into site/public/data.
- Python: uv run pytest -q runs everything.

## Global constraints (from the plan)

- Leagues: `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1. Second divisions for head to head only: `E1`, `SP2`, `I2`, `D2`, `F2`.
- Single data source: football-data.co.uk. Season file `https://www.football-data.co.uk/mmz4281/<code>/<div>.csv` (code `2627` = 2026/27; seasons start July 1). Fixtures `https://www.football-data.co.uk/fixtures.csv`. Both redirect (302); follow redirects. Files start with a UTF-8 BOM.
- Columns used: `Date, Time, HomeTeam, AwayTeam, FTHG, FTAG, HxG, AxG, HS, AS, HST, AST, HC, AC, HY, AY, HR, AR`. `HxG/AxG` may be empty in older seasons → `null`, never 0.
- Settlement (Betano, from the user): markets are **match totals**; shots and shots on target are separate markets and shots include shots on target; **cards: yellow = 1, red = 2**.
- Market lines (fixed in v1): match — goals 2.5, corners 9.5, cards 4.5, shots 24.5, shots on target 8.5; per team — goals 1.5, corners 4.5, cards 1.5, shots 12.5, shots on target 4.5. Plus 1X2 and BTTS.
- Both teams must be from the same league.
- Data freshness: once per night. "Today" = today's date in Europe/Madrid.
- No odds, no bookmaker scraping, no accounts, zero hosting cost.
- All code, UI copy and docs in English. Mobile-first single-column layout ("layout A": markets first, then season stats, last 6, head to head).
- Python tests: `uv run pytest -q`. Site tests: `cd site && npm test` (Vitest, `vitest run`).

## Review focus items (from the plan; cover the ones your task owns)

1. **A team in today's fixtures, or in the URL, that is not in the league's data** (typo, promoted team with no matches) — expected: the home list still renders; the match page shows "Team not found" instead of crashing. Test in Task 6.
2. **A team with zero home or zero away matches so far** (season start) — expected: per-side stats are `null`, rendered as "—", never `NaN`/`Infinity`. Tests in Task 5 and Task 6.
3. **One CSV download fails or returns garbage during the nightly run** — expected: the build fails validation and the previously published files stay untouched. Test in Task 7.
4. **Fewer than 6 previous matches or no head-to-head meetings** — expected: show what exists; "No previous meetings" when empty. Test in Task 6.
5. **Seasons without xG** — expected: `null` in JSON and "—" on the page; xG averages use only matches that have xG. Tests in Task 1, Task 5 and Task 6.

## Your task (verbatim from the plan)

### Task 7: `build-cli` — produce and validate the data files (Wave 3)

**Files:**
- Create: `src/matchstats/build.py`, `src/matchstats/cli.py`
- Modify: `pyproject.toml` (script `matchstats = "matchstats.cli:main"`), `uv.lock`
- Test: `tests/matchstats/test_build.py`

**Interfaces:**
- Consumes: T1 (`load_matches`, `download`, `parse_fixtures_csv`, `FIXTURES_URL`, leagues helpers), T3 `fit_goals_model`, T4 `fit_stat_model`, `STAT_FIELDS`, T5 functions.
- Produces:
  - `build(out_dir: Path, cache_dir: Path, today: date, loader: Callable[..., list[Match]] = load_matches, fixtures_text: Callable[[], str] | None = None) -> None`
  - `validate_output(directory: Path) -> list[str]` (problems; empty = valid)
  - `class BuildError(RuntimeError)`
  - CLI: `uv run matchstats build --out site/public/data --cache data/raw [--today YYYY-MM-DD]`, exit 0 on success, 1 on `BuildError` (message on stderr).

Behavior: current season = `season_code(today)`. For each top league: goals model fit on its top-division matches of the 3 most recent seasons with `ref_date = today`; stat models on the current and previous season; season stats and table from the current season; `last6` from the league's matches, all seasons loaded; head to head over the top + second division of the 10 most recent seasons, for every pair of current-season teams. `today` from fixtures filtered to the 5 leagues and today's date (Europe/Madrid). Write everything to `out_dir.parent / ".data-tmp"`, run `validate_output`. If it returns problems, delete the temp dir and raise `BuildError`, leaving `out_dir` untouched. Otherwise replace `out_dir` with the temp dir (`shutil.rmtree` + `rename`).

`validate_output` checks: `index.json` has the 5 leagues in order; each league has ≥ 16 teams; every team in `index` appears in that league's `goals.teams`, in all 4 `stats.*.teams`, and in `teams`; h2h has exactly `n(n-1)/2` pairs; all files parse as JSON; no `NaN`/`Infinity` (`json.dumps(..., allow_nan=False)`).

- [ ] **Step 1: Write failing tests** with a synthetic `loader` (18 teams per league, 2 seasons, rng 3) and fixed `fixtures_text`:
  - `test_build_writes_contract_files` — the three file kinds exist for all 5 leagues; top-level keys match the contract example files (recursive key-set comparison on the first team/pair).
  - `test_today_filtered_to_top_leagues_and_date`.
  - `test_failed_validation_keeps_previous_output` (Review Focus 3) — pre-populate `out_dir` with a marker file; a loader returning only 3 teams for one league → `BuildError`, the marker file still exists, no `.data-tmp` left.
  - `test_cli_exit_codes` — `main(["build", ...])` returns 0 and 1 for the two cases above.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** `uv run pytest -q` → PASS. **Step 5:** Commit `feat(matchstats): add build command with output validation`.
