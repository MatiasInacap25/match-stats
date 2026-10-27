# Task 5: team-stats

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `src/matchstats/team_stats.py`
- `tests/matchstats/test_team_stats.py`

## Test command (must pass before you finish)

`uv run pytest -q`

## Notes from earlier waves (binding)

- Match.season holds the season code (e.g. "2627"), not the label; use leagues.season_label() for display.
- ingest.parse_season_csv skips played rows with blank or invalid count stats (logged warning); blank HxG/AxG is None.
- Contract update: in season.<all|home|away>, when matches == 0 every per-match average and *_pct is null; counts are 0; position/points keep the table values. site/src/lib/types.ts SeasonSide already reflects this.
- site/src/lib/probability.ts goalLambdas throws Error('Unknown team: <name>') for a team not in goals.teams; check membership first.
- site/src/lib/probability.ts teamGoalsOver uses goals > line (exact for half-lines).
- Python: uv run pytest -q runs everything. Site: cd site && npm ci first in a fresh worktree, then npm test.
- site/public/data/ is produced by the nightly job: never commit files there (dev:example copies example data into it for local use only).

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

### Task 5: `team-stats` — season stats, table, last 6, head to head (Wave 2)

**Files:** Create `src/matchstats/team_stats.py`. Test `tests/matchstats/test_team_stats.py`.

**Interfaces:**
- Consumes: `Match` (T1).
- Produces: `league_table(matches: list[Match]) -> dict[str, tuple[int, int]]` (team → (position, points); 3/1/0 points; ties by goal difference, then goals for, then name), `season_stats(matches: list[Match], team: str, table: dict[str, tuple[int, int]]) -> dict` (contract `season` object with `all`/`home`/`away`), `last_matches(matches: list[Match], team: str, n: int = 6) -> list[dict]` (contract `last6` items, newest first), `pair_key(a: str, b: str) -> str`, `head_to_head(matches: list[Match], a: str, b: str) -> list[dict]` (contract meeting items, newest first).

- [ ] **Step 1: Write failing tests** with hand-made matches:
  - `test_table_points_and_tiebreak`.
  - `test_season_stats_values` — goals/xG/shots/SoT/corners per-match averages, `yellow_cards`/`red_cards` raw per match, `btts_pct`, `over_2_5_pct`, `clean_sheets`, W-D-L.
  - `test_home_away_split` — `home` uses only home matches.
  - `test_side_without_matches_is_null` (Review Focus 2) — a team with no away matches: `away.matches == 0` and every per-match average is `None` (no `ZeroDivisionError`); `position`/`points` still set.
  - `test_xg_average_ignores_missing` (Review Focus 5) — 2 matches with xG and 1 without → average of the 2; all missing → `None`.
  - `test_last6_newest_first_and_points` — 8 matches → 6 returned, newest first; `cards_for` = yellow + 2 × red; `venue`, `result` correct.
  - `test_head_to_head_both_venues_newest_first` — includes matches with either team at home, across divisions; `pair_key("Chelsea", "Arsenal") == "Arsenal|Chelsea"`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement (round floats to 2 decimals, pct to 3). **Step 4:** Run → PASS, then `uv run pytest -q`. **Step 5:** Commit `feat(matchstats): add season stats, last six and head to head`.
