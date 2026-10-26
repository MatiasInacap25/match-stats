# Match Stats Site Implementation Plan

> **For agentic workers:** this plan runs through `orchestrate-waves` (project skill): one Haiku worker per task, tasks in the same wave in parallel. Read the spec and `contract/data-contract.md` before your task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A free static site where the user picks two teams from the same top-5 league and sees market probabilities (match and per-team), season stats, the last 6 matches of each team, and head to head. A nightly job refreshes the data.

**Architecture:** A Python package `matchstats` downloads football-data.co.uk CSVs, fits a Dixon-Coles goals model and negative-binomial stat rates per league, computes season stats, last-6 and head to head, and writes the JSON files defined in `contract/data-contract.md` to `site/public/data/`. An Astro site in `site/` reads those files and computes all probabilities in the browser. GitHub Actions runs the build nightly and commits the data; Vercel redeploys on commit.

**Tech Stack:** Python 3.12+, uv, numpy, scipy, pytest. Node 26, npm, Astro (latest), TypeScript, Vitest. GitHub Actions, Vercel.

**Spec:** `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1). **Contract:** `contract/data-contract.md` + `contract/example/` — binding for both sides.

## Global Constraints

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

## Review Focus

1. **A team in today's fixtures, or in the URL, that is not in the league's data** (typo, promoted team with no matches) — expected: the home list still renders; the match page shows "Team not found" instead of crashing. Test in Task 6.
2. **A team with zero home or zero away matches so far** (season start) — expected: per-side stats are `null`, rendered as "—", never `NaN`/`Infinity`. Tests in Task 5 and Task 6.
3. **One CSV download fails or returns garbage during the nightly run** — expected: the build fails validation and the previously published files stay untouched. Test in Task 7.
4. **Fewer than 6 previous matches or no head-to-head meetings** — expected: show what exists; "No previous meetings" when empty. Test in Task 6.
5. **Seasons without xG** — expected: `null` in JSON and "—" on the page; xG averages use only matches that have xG. Tests in Task 1, Task 5 and Task 6.

---

## Waves

| Wave | Tasks (parallel) | Depends on |
|------|------------------|------------|
| 1 | T1 `ingest`, T2 `site-core` | contract |
| 2 | T3 `goals-model`, T4 `stat-model`, T5 `team-stats`, T6 `site-pages` | W1 |
| 3 | T7 `build-cli`, T8 `backtest`, T9 `nightly-deploy` | W2 |
| 4 | Integration (orchestrator, not a worker) | W3 |

Edit surfaces are disjoint within each wave. Only T1 (W1) and T7 (W3) touch `pyproject.toml`/`uv.lock`; only T1 touches the root `.gitignore`.

---

### Task 1: `ingest` — leagues, match model, CSV download and parsing (Wave 1)

**Files:**
- Modify: `pyproject.toml` (add `src/matchstats` to `[tool.hatch.build.targets.wheel] packages`; dependencies `numpy>=2`, `scipy>=1.14`), `uv.lock`, `.gitignore` (add `data/raw/`)
- Create: `src/matchstats/__init__.py`, `src/matchstats/leagues.py`, `src/matchstats/match.py`, `src/matchstats/ingest.py`
- Test: `tests/matchstats/test_leagues.py`, `tests/matchstats/test_ingest.py`, `tests/matchstats/fixtures/E0_2627_sample.csv`, `tests/matchstats/fixtures/fixtures_sample.csv`

**Interfaces — Produces:**
- `leagues.py`: `TOP_LEAGUES: dict[str, str]` (code → name, in the Global Constraints order), `SECOND_DIVISION: dict[str, str]` (`{"E0": "E1", "SP1": "SP2", "I1": "I2", "D1": "D2", "F1": "F2"}`), `season_code(d: date) -> str`, `season_label(code: str) -> str` (`"2627"` → `"2026/27"`), `recent_seasons(current: str, n: int) -> list[str]` (newest first, includes current).
- `match.py`: `@dataclass(frozen=True) class Match` with fields `div: str, season: str, date: date, home: str, away: str, home_goals: int, away_goals: int, home_xg: float | None, away_xg: float | None, home_shots: int, away_shots: int, home_sot: int, away_sot: int, home_corners: int, away_corners: int, home_yellow: int, away_yellow: int, home_red: int, away_red: int` and properties `home_cards`/`away_cards` (`yellow + 2 * red`). `@dataclass(frozen=True) class Fixture: div: str, date: date, time: str, home: str, away: str`.
- `ingest.py`: `season_url(code: str, div: str) -> str`, `FIXTURES_URL: str`, `parse_season_csv(text: str, div: str, season: str) -> list[Match]`, `parse_fixtures_csv(text: str) -> list[Fixture]`, `download(url: str, cache_file: Path, refresh: bool) -> str | None` (returns `None` on HTTP 404), `load_matches(divs: list[str], seasons: list[str], cache_dir: Path, current_season: str) -> list[Match]`, `class IngestError(RuntimeError)`.

- [ ] **Step 1: Capture fixtures.** Download the real `E0` 2026/27 file and `fixtures.csv` (follow redirects). Save the header plus 5 data rows of each as the two fixture files. Add one extra row to the season sample with empty `HxG`/`AxG`, and one with an empty `FTHG` (a postponed match).
- [ ] **Step 2: Write failing tests:**
  - `test_season_code_boundaries` — `season_code(date(2026, 6, 30)) == "2526"`, `season_code(date(2026, 7, 1)) == "2627"`; `season_label("2627") == "2026/27"`; `recent_seasons("2627", 3) == ["2627", "2526", "2425"]`.
  - `test_parse_season_csv_real_sample` — the 5 real rows parse; the first row's teams, goals, `HS/HST/HC/HY/HR` equal the CSV values; `date` is a `datetime.date`.
  - `test_cards_are_points` — a match with 2 yellow + 1 red home has `home_cards == 4`.
  - `test_missing_xg_is_none` — the empty-xG row gives `home_xg is None`.
  - `test_skips_rows_without_result` — the empty `FTHG` row is not returned.
  - `test_two_digit_year` — `"25/10/26"` parses to `date(2026, 10, 25)`.
  - `test_parse_fixtures` — the sample returns `Fixture` objects with the right `div`, `date`, `time`, `home`, `away`.
  - `test_download_uses_cache_unless_refresh` — monkeypatch `urllib.request.urlopen`: an existing cache file with `refresh=False` → no network call; `refresh=True` → one call, and the cache file is rewritten.
  - `test_download_404_returns_none`, and `test_load_matches_skips_missing_season` — a 404 for one season is skipped; the others load.
  - `test_download_retries_then_raises` — 3 failed attempts (non-404 error) → `IngestError`.
- [ ] **Step 3:** Run `uv run pytest tests/matchstats -q` → FAIL.
- [ ] **Step 4:** Implement. `download`: `urllib.request` (follows redirects), header `User-Agent: matchstats/0.1`, timeout 30 s, 3 attempts with 2 s back-off, 1 s pause after every network call (be polite to the free site), write the cache file only after a successful read. `load_matches` refreshes only files of `current_season` and caches the rest under `cache_dir/<season>/<div>.csv`. Decode with `utf-8-sig`.
- [ ] **Step 5:** Run `uv run pytest -q` → all PASS (orchestra tests included).
- [ ] **Step 6:** Commit `feat(matchstats): ingest football-data CSVs`.

---

### Task 2: `site-core` — Astro scaffold, contract types, probability math (Wave 1)

**Files:**
- Create: `site/` Astro project (`package.json`, `package-lock.json`, `astro.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `.gitignore` with `node_modules/` and `dist/`, `src/pages/index.astro` placeholder), `site/src/lib/types.ts`, `site/src/lib/probability.ts`
- Test: `site/test/probability.test.ts`, `site/test/types.test.ts`

**Interfaces — Produces:**
- `types.ts`: `StatName = "corners" | "cards" | "shots" | "shots_on_target"`, `IndexData`, `LeagueData`, `GoalsModel`, `StatModel`, `TeamSeason` (`{all, home, away}` of `SeasonSide`), `SeasonSide`, `LastMatch`, `H2HData`, `Meeting` — field names exactly as `contract/data-contract.md`, nullable fields typed `number | null`.
- `probability.ts`:
  - `poissonPmf(k: number, mu: number): number`
  - `negBinPmf(k: number, mu: number, size: number | null): number` — `size === null` → Poisson.
  - `probOver(line: number, mu: number, size: number | null): number` — `P(X > line)` = `1 - CDF(floor(line))`.
  - `goalLambdas(goals: GoalsModel, home: string, away: string): { home: number; away: number }` — formula from the contract.
  - `scoreMatrix(lambdaHome: number, lambdaAway: number, rho: number, maxGoals = 10): number[][]` — Poisson × Poisson with Dixon-Coles `tau`, renormalized to sum 1.
  - `goalMarkets(matrix: number[][]): { home: number; draw: number; away: number; over2_5: number; btts: number }`
  - `teamGoalsOver(matrix: number[][], side: "home" | "away", line: number): number`

- [ ] **Step 1:** `npm create astro@latest site -- --template minimal --no-install --no-git --skip-houston --yes`, then `cd site && npm install && npm install -D vitest`. Add `"test": "vitest run"` to `package.json`. Run `npm run build` → succeeds.
- [ ] **Step 2: Write failing tests:**
  - `poissonPmf(0, 1)` ≈ `Math.exp(-1)` (1e-12); `sum_{k<=50} poissonPmf(k, 3.2)` ≈ 1.
  - `negBinPmf` with `size = 1e9` ≈ `poissonPmf` (1e-6); mean of `negBinPmf(k, 4, 2)` over k ≤ 200 ≈ 4 (1e-6); variance ≈ `4 + 16/2` (1e-4).
  - `probOver(2.5, 2.5, null)` ≈ `0.4562` (1e-4).
  - `tau` behavior through `scoreMatrix`: with `rho = 0` the matrix equals the plain Poisson product, renormalized; the matrix sums to 1 (1e-9) for `rho = -0.1`.
  - Symmetric teams (equal attack/defense, `home_advantage = 0`, `rho = 0`) → `home ≈ away`; `home + draw + away ≈ 1`.
  - `goalLambdas` on `contract/example/leagues/E0.json` for Arsenal–Brighton equals `exp(0.35 + 0.05 + 0.25)` and `exp(0.0 - 0.30)`.
  - `types.test.ts`: the three example files load and type-check through a `satisfies`-style assignment (compile error = failure via `tsc --noEmit` in `npm test`; add `"test": "tsc --noEmit && vitest run"`).
- [ ] **Step 3:** `cd site && npm test` → FAIL.
- [ ] **Step 4:** Implement. Dixon-Coles `tau(x, y)`: `(0,0) → 1 - lh*la*rho`, `(0,1) → 1 + lh*rho`, `(1,0) → 1 + la*rho`, `(1,1) → 1 - rho`, otherwise 1. Use log-space or iterative pmf to avoid factorial overflow.
- [ ] **Step 5:** `npm test` → PASS; `npm run build` → succeeds.
- [ ] **Step 6:** Commit `feat(site): scaffold Astro site with contract types and probability math`.

---

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

---

### Task 4: `stat-model` — corners, cards, shots, shots on target (Wave 2)

**Files:** Create `src/matchstats/stat_model.py`. Test `tests/matchstats/test_stat_model.py`.

**Interfaces:**
- Consumes: `Match` (T1).
- Produces: `STAT_FIELDS: dict[str, tuple[str, str]] = {"corners": ("home_corners", "away_corners"), "cards": ("home_cards", "away_cards"), "shots": ("home_shots", "away_shots"), "shots_on_target": ("home_sot", "away_sot")}`; `fit_stat_model(matches: list[Match], stat: str, current_season: str, shrink: float = 5.0) -> dict` returning one contract `stats.<name>` object.

Rules: match weight 1.0 if `match.season == current_season` else 0.5. `avg_home`/`avg_away` = weighted means of the home/away side's count. Per team, raw ratio = weighted mean ÷ the matching league average (`home_for` vs `avg_home`, `home_against` vs `avg_away`, `away_for` vs `avg_away`, `away_against` vs `avg_home`), shrunk: `(w * raw + shrink * 1.0) / (w + shrink)` with `w` = sum of that team's weights on that side. Dispersion (method of moments, using the fitted ratios): for each team count `x_i` with expected `mu_i` (contract formula), `size = sum(mu_i²) / sum((x_i - mu_i)² - mu_i)` when the denominator is > 0, else `null`. Same for match totals, with `mu_i = mu_home + mu_away`. Round to 4 decimals.

- [ ] **Step 1: Write failing tests:**
  - `test_league_averages` — on hand-made matches, `avg_home`/`avg_away` equal the weighted means.
  - `test_previous_season_half_weight`.
  - `test_ratio_shrinks_toward_one` — a team with 2 home matches at double the average gets `1 < home_for < 2`.
  - `test_cards_use_points` — red cards count 2 through `home_cards`.
  - `test_overdispersed_data_gives_finite_size` — NB-generated counts (`size=3`, rng 11) give a size between 1.5 and 6; Poisson-generated counts give `None` or > 30.
  - `test_output_shape_matches_contract` — keys equal the contract example's `stats.corners` keys; every team present with the 4 ratios.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS, then `uv run pytest -q`. **Step 5:** Commit `feat(matchstats): add stat rate models`.

---

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

---

### Task 6: `site-pages` — markets, rendering, home and match pages (Wave 2)

**Files:**
- Create: `site/src/lib/markets.ts`, `site/src/lib/render.ts`, `site/src/lib/data.ts`, `site/src/pages/match.astro`, `site/src/styles/global.css`, `site/scripts/use-example-data.mjs` (copies `contract/example/` → `site/public/data/` for local dev; `npm run dev:example`)
- Modify: `site/src/pages/index.astro`, `site/package.json` (script `dev:example` only)
- Test: `site/test/markets.test.ts`, `site/test/render.test.ts`

**Interfaces:**
- Consumes: `types.ts`, `probability.ts` (T2); data files per the contract.
- Produces:
  - `markets.ts`: `interface Market { id: string; label: string; scope: "match" | "home" | "away"; line: number | null; expected: number | null; probability: number }`; `MATCH_LINES` and `TEAM_LINES` with the Global Constraints values; `matchMarkets(league: LeagueData, home: string, away: string): Market[]` — 1X2 (three markets `1`, `X`, `2`), BTTS, goals over (match + each team), and for each `StatName` match-total over and each team's over, with `expected` = the mean used. Throws `TeamNotFoundError` when a team is missing from `league.goals.teams`.
  - `render.ts` (pure, returns HTML strings): `renderMarkets(markets: Market[], home: string, away: string)`, `renderSeasonTable(home: TeamSeason, away: TeamSeason, side: "all" | "home" | "away", names: [string, string])`, `renderLastMatches(team: string, matches: LastMatch[])`, `renderHeadToHead(meetings: Meeting[], home: string, away: string)` (rows + summary over the last 6: wins per team, draws, average goals, BTTS count), `formatValue(v: number | null, digits?: number): string` (`null`/non-finite → `"—"`), `formatPct(p: number): string` (`"62%"`).
  - `data.ts`: `loadIndex()`, `loadLeague(code)`, `loadHeadToHead(code)` — fetch from `${import.meta.env.BASE_URL}data/...`.

Pages (client-side scripts, English copy, single column, readable at 360 px width):
- `index.astro`: header "Match Stats", league `<select>`, home/away `<select>`s listing only that league's teams, "Analyze" → `/match?league=<code>&home=<team>&away=<team>` (disabled when home == away). Section "Today · updated HH:MM" (Europe/Madrid, from `generated_at`): one row per `today` match with `1` and `Over 2.5` probabilities, linking to its match page. Empty list → "No fixtures data for today". A today match whose team is missing → row shown without probabilities, still linked.
- `match.astro`: reads the query, loads league + h2h, renders in order: markets (match first, then per-team), season stats with an All/Home/Away toggle, last 6 of each team, head to head. Missing team → "Team not found" + link home.

- [ ] **Step 1: Write failing tests** (load `contract/example/` with `fs`):
  - `test 1X2 + BTTS + goal markets from example` — `1+X+2 ≈ 1`; probabilities in (0,1); lines equal the Global Constraints.
  - `test stat markets expected values` — Arsenal–Brighton corners: home expected = `5.6 * 1.2 * 1.1`, away = `4.6 * 0.9 * 0.8`; match total `probOver(9.5, sum, 15.0)`; cards use Poisson because the example's cards dispersion is `null`.
  - `test missing team throws TeamNotFoundError` (Review Focus 1).
  - `test formatValue null and NaN render dash` (Review Focus 2, 5).
  - `test season table renders dash for null xG` — Chelsea `away` has `xg_for: null` → "—".
  - `test head to head empty` (Review Focus 4) — `Arsenal|Chelsea` is empty → "No previous meetings".
  - `test head to head summary` — `Arsenal|Brighton`: Arsenal 1 win, 1 draw, average goals 2.5, BTTS 2/2.
- [ ] **Step 2:** `cd site && npm test` → FAIL. **Step 3:** Implement. **Step 4:** `npm test` → PASS; `npm run dev:example` then `npm run build` → succeeds. **Step 5:** Commit `feat(site): add markets, match page and home page`.

---

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

---

### Task 8: `backtest` — is the goals model sane? (Wave 3)

**Files:** Create `src/matchstats/backtest.py`. Test `tests/matchstats/test_backtest.py`.

**Interfaces:**
- Consumes: `Match`, `load_matches`, leagues helpers (T1), `fit_goals_model` (T3).
- Produces: `predict_1x2(goals: dict, home: str, away: str) -> tuple[float, float, float]` (Dixon-Coles score matrix, same formulas as the contract and `site/src/lib/probability.ts`), `evaluate(matches: list[Match], refit_every_days: int = 14, warmup_days: int = 60) -> dict` with `n`, `log_loss`, `brier`, `baseline_log_loss`, `baseline_brier` (baseline = home/draw/away frequencies of the matches before each prediction); CLI `uv run python -m matchstats.backtest --league E0 --season 2526 --cache data/raw` printing those numbers.

Walk-forward: sort matches by date; after `warmup_days`, refit every `refit_every_days` on all earlier matches (`ref_date` = refit date) and predict matches until the next refit. Teams unknown to the current fit are skipped (counted in an `skipped` field).

- [ ] **Step 1: Write failing tests:** `test_predict_1x2_sums_to_one`; `test_model_beats_baseline_on_synthetic_strengths` (rng 5, strong/weak teams → `log_loss < baseline_log_loss`); `test_no_lookahead` — predictions for a date use only earlier matches (spy on the fit inputs).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** `uv run pytest -q` → PASS. **Step 5:** Commit `feat(matchstats): add walk-forward backtest`.

---

### Task 9: `nightly-deploy` — GitHub Actions job, Vercel config, README (Wave 3)

**Files:**
- Create: `.github/workflows/nightly.yml`, `site/vercel.json`, `README.md`
- Test: `tests/test_workflow.py`

`nightly.yml`:
- `on: schedule: - cron: "0 2 * * *"` (≈ 04:00 Europe/Madrid in summer, 03:00 in winter) and `workflow_dispatch`.
- `permissions: contents: write`.
- Steps: `actions/checkout@v4`; `astral-sh/setup-uv@v6`; `actions/cache@v4` for `data/raw` (key `raw-${{ github.run_id }}`, restore-keys `raw-`); `uv sync --frozen`; `uv run matchstats build --out site/public/data --cache data/raw`; if `git status --porcelain site/public/data` is non-empty: configure `github-actions[bot]`, commit `chore(data): nightly update`, `git push`. A failed build fails the job and commits nothing.

`site/vercel.json`: `{"buildCommand": "npm run build", "outputDirectory": "dist", "installCommand": "npm ci"}`.

`README.md`: what the project is; local use (`uv run matchstats build --out site/public/data --cache data/raw`, `cd site && npm run dev`); `npm run dev:example`; the backtest command; the orchestra workflow (link `waves/README.md`); **user-only steps**: create the GitHub repo under your account and push, import it in Vercel with root directory `site`, and in the repo settings allow Actions "Read and write permissions". Known limitation: how football-data.co.uk records a second yellow (in `HY`, `HR` or both) is not verified; cards are counted as `HY + 2 × HR`.

- [ ] **Step 1: Write failing tests** (plain text assertions, no YAML lib): cron string `0 2 * * *`; `workflow_dispatch`; `contents: write`; the exact build command; the commit message; the push happens only behind the porcelain check; `vercel.json` parses and has the three keys.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Write the files. **Step 4:** `uv run pytest -q` → PASS. **Step 5:** Commit `ci: add nightly data job and deploy config`.

---

### Wave 4: Integration (orchestrator)

- [ ] Run `uv run matchstats build --out site/public/data --cache data/raw` against the real source. Expected: exit 0 and 5 leagues with 18–20 teams each.
- [ ] Run `uv run python -m matchstats.backtest --league E0 --season 2526 --cache data/raw` and record the log loss vs the baseline in the README.
- [ ] `cd site && npm run build && npm run preview`; open the home page and one match page at phone width; check today's list, the markets, the season toggle, last 6 and head to head against football-data numbers for one team.
- [ ] Commit the first data snapshot: `chore(data): initial data`.
- [ ] Hand the user the user-only steps from the README.
