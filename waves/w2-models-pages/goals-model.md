# Task 3: goals-model

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `src/matchstats/goals_model.py`
- `tests/matchstats/test_goals_model.py`

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

### Task 3: `goals-model` — Dixon-Coles fit (Wave 2)

**Files:** Create `src/matchstats/goals_model.py`. Test `tests/matchstats/test_goals_model.py`.

**Interfaces:**
- Consumes: `Match` (T1).
- Produces: `fit_goals_model(matches: list[Match], ref_date: date, xi: float = 0.002, l2: float = 0.1) -> dict` returning exactly the contract's `goals` object (`home_advantage`, `rho`, `teams: {name: {attack, defense}}`), floats rounded to 4 decimals.

- [ ] **Step 1: Write failing tests** (synthetic data from `numpy.random.default_rng(7)`, 6 teams × 3 double round-robins with known attack/defense, home advantage 0.3):
  - `test_recovers_home_advantage` — within 0.1 of 0.3.
  - `test_recovers_team_order` — fitted attack order equals the true order.
  - `test_attack_sums_to_zero` — `abs(sum(attack)) < 1e-6`.
  - `test_rho_bounded` — `-0.2 <= rho <= 0.2`.
  - `test_time_decay_weights_recent_matches` — when a team's recent matches are all big wins and old ones losses, its attack with `xi=0.01` is higher than with `xi=0`.
  - `test_output_shape_matches_contract` — keys equal the contract example's `goals` keys; every team in the matches is present.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement: weighted Dixon-Coles log-likelihood (weights `exp(-xi * days_before_ref_date)`), parameters attack/defense per team + home advantage + rho, `scipy.optimize.minimize(method="L-BFGS-B")` with rho bounds `[-0.2, 0.2]`, L2 penalty `l2 * sum(attack² + defense²)`, then center attack (subtract its mean, add the same to defense to keep lambdas). **Step 4:** Run → PASS, then `uv run pytest -q`. **Step 5:** Commit `feat(matchstats): add Dixon-Coles goals model`.
