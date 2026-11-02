# UEFA Cross-League Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. In this repo, tasks run as Haiku workers through `uv run orchestra run-wave` (skill `orchestrate-waves`); each wave below is one manifest.

**Goal:** Market probabilities for UEFA matches between teams of different leagues, four new full leagues (N1, B1, T1, G1), and goals-only data for Norway and Austria.

**Architecture:** A league registry replaces the hard-coded 7 leagues in the Python build; goals-only leagues come from football-data's `new/<CC>.csv`; a new UEFA strength module fits per-league attack/defense offsets on past UEFA results and writes `uefa.json`; the site computes cross-league markets in the browser from both teams' league files plus `uefa.json`.

**Tech Stack:** Python 3 (uv, numpy, scipy, pytest), Astro + TypeScript (vitest).

**Spec:** `docs/superpowers/specs/2026-11-02-uefa-cross-league-design.md`

## Global Constraints

- Free, keyless sources only. football-data URLs redirect (302); the existing `download()` already follows them.
- The 7 current leagues (`E0, SP1, I1, D1, F1, E1, P1`) stay hard requirements; their modelling and output must not change.
- New leagues are soft: unreachable source → cached CSV if present; still no usable data or failed validation → league dropped with a warning, build continues.
- Site order: `E0, SP1, I1, D1, F1, E1, P1, N1, B1, T1, G1, UCL, UEL, UECL, DFB`. `NOR` and `AUT` are data-only (no chip, not in `index.leagues`, not in the comparator).
- Minimum teams: 16 for every league except `G1` 14, `AUT` 12, `NOR` 16.
- All UI copy in Spanish; code, comments and tests in English.
- Same-league UEFA pairs keep the existing domestic model and page.
- Every new contract field is documented in `contract/data-contract.md` in the same task that writes it.

## Review Focus

1. A UEFA feed name that resolves in more than one league (e.g. a generic "Sporting") → `home_league`/`away_league` is `null`, never a guess. Test in Task 4.
2. An optional league dropped on a bad night, or an old match-page URL naming a league whose file is gone → the calendar shows the row without link/probabilities and the match page shows its normal error message, no crash. Tests in Task 1 (build) and Task 5 (page).
3. A goals-only team (Bodø/Glimt) on the UEFA page → stat rows show "—" and stat markets are hidden, never `NaN`. Tests in Task 5 and Task 7.
4. A goals-only league between seasons (Norway in winter, its newest season already finished) → "current season" is the newest season in the file, season stats still render. Test in Task 2.
5. `uefa.json` missing, unreadable or `"calibrated": false` → UEFA matches show data without probabilities. Tests in Task 7.

---

## Shared interfaces (fixed here so parallel tasks agree)

**Python registry** (`src/matchstats/leagues.py`, Task 1):

```python
@dataclass(frozen=True)
class LeagueSpec:
    code: str              # "N1", "NOR"
    name: str              # "Eredivisie"
    divisions: tuple[str, ...]  # head-to-head divisions, as COUNTRY_DIVISIONS today
    source: Literal["full", "goals_only"]
    min_teams: int
    in_site: bool          # full league in the site (chip, calendar, comparator)
    required: bool         # True only for the original 7
    fixture_slug: str | None  # fixturedownload slug, None -> fixtures.csv
    new_csv: str | None    # "NOR"/"AUT" for goals-only, else None

LEAGUES: tuple[LeagueSpec, ...]   # order: E0 SP1 I1 D1 F1 E1 P1 N1 B1 T1 G1 NOR AUT
TOP_LEAGUES: dict[str, str]       # unchanged: the 7 required, code -> name
SITE_LEAGUES: dict[str, str]      # the 11 in_site leagues, in order
DATA_LEAGUES: dict[str, str]      # all 13, in order
```

**Goals-only ingest** (`src/matchstats/ingest.py`, Task 2):

```python
def goals_only_url(country: str) -> str          # "https://www.football-data.co.uk/new/NOR.csv"
def parse_goals_only_csv(text: str, div: str) -> list[Match]
def load_goals_only(country: str, div: str, cache_dir: Path) -> list[Match]   # refreshes; cached copy on failure; [] when none
```

`Match` stat fields (`home_shots … away_red`) become `int | None`; `home_xg`/`away_xg` already are. Goals-only rows have all of them `None`. `Match.season` for goals-only rows is the file's `Season` value normalised to football-data style when it is `YYYY/YYYY` (`"2026/2027"` → `"2627"`), and kept as the 4-digit year otherwise (`"2026"`).

**Contract additions** (written by Tasks 1, 4, 6; read by Tasks 3, 5, 7):

- `index.json` → `leagues`: the 7 required in order, then present optional site leagues in registry order.
- `leagues/<code>.json` for goals-only leagues: no `stats` key; season-side stat fields and `last6` stat fields are `null`; `season` is `"2026"` (NOR) or `"2026/27"` (AUT).
- `upcoming[]` UEFA items gain `home_league` and `away_league`: the code (of the 13 `DATA_LEAGUES`) whose current teams uniquely contain that team, else `null`. League items: both equal the league code. DFB items: both `null`.
- `uefa.json`:

```json
{
  "calibrated": true,
  "home_advantage": 0.21,
  "offsets": {"E0": {"attack": 0.0, "defense": 0.0}, "T1": {"attack": -0.18, "defense": 0.15}},
  "seasons": [2023, 2024, 2025],
  "backtest": {"held_out": 2025, "matches": 189, "log_loss": 0.99, "log_loss_unadjusted": 1.02, "log_loss_baseline": 1.07}
}
```

Cross-league goals model (site, Task 7): for H in league `LH`, A in `LA`:
`lambda_home = exp(attack[H] + offsets[LH].attack + defense[A] + offsets[LA].defense + home_advantage)`,
`lambda_away = exp(attack[A] + offsets[LA].attack + defense[H] + offsets[LH].defense)`,
`rho` = mean of the two leagues' `rho`. A league missing from `offsets` means no probabilities for that match.

**Match page URL for UEFA** (Task 5): `match?competition=UCL&home=<name>&home_league=<code>&away=<name>&away_league=<code>`. The existing `?league=&home=&away=` form is unchanged.

---

## Wave w14

### Task 1: league-registry (Python, 4 new full leagues)

**Files:**
- Modify: `src/matchstats/leagues.py`, `src/matchstats/build.py`, `src/matchstats/fixture_sources.py`, `src/matchstats/team_names.py`, `contract/data-contract.md`
- Test: `tests/matchstats/test_build.py`, `tests/matchstats/test_leagues.py`, `tests/matchstats/test_fixture_sources.py`, `tests/matchstats/test_team_names.py`

**Interfaces:**
- Produces: `LeagueSpec`, `LEAGUES`, `TOP_LEAGUES`, `SITE_LEAGUES`, `DATA_LEAGUES` (above). `league_fixture_urls(season)` returns the 9 site leagues that have a `fixture_slug` (N1 `eredivisie`, T1 `super-lig`; B1 and G1 have none and use `fixtures.csv`).
- Goals-only entries (`NOR`, `AUT`) are declared in `LEAGUES` but `build.py` skips `source == "goals_only"` until Task 4.

- [ ] **Step 1: Write failing tests**
  - `test_registry_order_and_flags`: `[l.code for l in LEAGUES] == ["E0","SP1","I1","D1","F1","E1","P1","N1","B1","T1","G1","NOR","AUT"]`; `required` true exactly for the first 7; `in_site` false exactly for NOR, AUT; `min_teams` of G1 is 14, AUT 12.
  - `test_new_leagues_written`: synthetic loader with N1/B1/T1/G1 matches → `index.json` `leagues` codes are the 11 in order and `leagues/N1.json`, `h2h/N1.json` exist with the existing shape.
  - `test_optional_league_without_data_is_dropped`: loader returns nothing for B1 → build succeeds, B1 absent from `index.leagues`, warning logged containing `B1`.
  - `test_optional_league_failing_validation_is_dropped`: G1 with 10 teams → dropped with warning, build succeeds.
  - `test_required_league_still_fails_build`: no E0 data → `BuildError` (existing behaviour).
  - `test_upcoming_includes_new_league_matches`: an N1 fixturedownload row and a B1 `fixtures.csv` row appear in `upcoming` with `competition` `N1`/`B1`, `league` equal to the code.
  - Existing tests pass unchanged.
- [ ] **Step 2: Run** `uv run pytest -q` → the new tests fail.
- [ ] **Step 3: Implement** the registry; make `build._write_files`, `validate_output`, `_upcoming_fixtures`, `COMPETITION_NAMES`/`COMPETITION_ORDER` iterate the registry (`SITE_LEAGUES` for site leagues); per-league `min_teams`; optional leagues built inside a try that drops them with `logger.warning` on `ValueError`/`IngestError`/validation problems. `_shared_league` and name resolution use `SITE_LEAGUES`.
- [ ] **Step 4: Aliases.** Download `eredivisie-2026` and `super-lig-2026` feeds and the current `N1/B1/T1/G1` CSVs and `fixtures.csv`; add an alias for every feed name that does not resolve to a current team. A test lists them (same pattern as the Championship/Primeira test).
- [ ] **Step 5: Contract.** Update `leagues`, `upcoming` sources and order lines in `contract/data-contract.md`.
- [ ] **Step 6: Run** `uv run pytest -q` → all pass. Run a real build into a temp dir (`uv run matchstats build --out <tmp>/data --cache data/raw`) and report its wall time and the team counts of the 4 new leagues in `RESULT.md`.
- [ ] **Step 7: Commit** `feat(matchstats): league registry with eredivisie, pro league, super lig and greek super league`.

### Task 2: goals-only-ingest (Python)

**Files:**
- Modify: `src/matchstats/match.py`, `src/matchstats/ingest.py`, `src/matchstats/team_stats.py`
- Create: `tests/matchstats/fixtures/new_nor_sample.csv`, `tests/matchstats/fixtures/new_aut_sample.csv` (trimmed real rows, header verbatim)
- Test: `tests/matchstats/test_ingest.py`, `tests/matchstats/test_team_stats.py`

**Interfaces:** Produces `goals_only_url`, `parse_goals_only_csv`, `load_goals_only` and the optional `Match` stat fields (above).

- [ ] **Step 1: Write failing tests**
  - `test_parse_goals_only_csv_nor`: rows map to `Match(div="NOR", season="2026", home_goals=…, home_shots=None, home_xg=None, …)`; rows without `HG`/`AG` skipped; date `DD/MM/YYYY` parsed.
  - `test_parse_goals_only_csv_aut_season_code`: `"2026/2027"` → `season == "2627"`.
  - `test_goals_only_url`: `goals_only_url("NOR") == "https://www.football-data.co.uk/new/NOR.csv"`.
  - `test_season_stats_goals_only`: season stats of a goals-only team have `matches`, `won`, `points`, `goals_for`, `btts_pct`, `over_2_5_pct`, `clean_sheets` filled and `xg_for`, `shots_for`, `corners_for`, `yellow_cards`, `red_cards` equal `None`.
  - `test_last_matches_goals_only`: stat fields `None`, score and `result` filled.
  - `test_head_to_head_goals_only`: works on goals-only matches.
  - `test_cards_property_none`: `home_cards` is `None` when yellow/red are `None`.
  - Existing tests pass unchanged (full-league outputs identical).
- [ ] **Step 2: Run** `uv run pytest -q` → new tests fail.
- [ ] **Step 3: Implement.** Stat fields `int | None`; `team_stats` averages skip `None` and return `None` when no value exists; `load_goals_only` uses `download(..., refresh=True)` with cache file `cache_dir / "new" / f"{country}.csv"` and returns `[]` on 404.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `feat(matchstats): goals-only league ingest`.

### Task 3: site-new-leagues (site)

**Files:**
- Modify: `site/src/lib/leagues.ts`, `site/src/lib/types.ts`
- Test: `site/test/leagues.test.ts`, `site/test/types.test.ts`

- [ ] **Step 1: Failing tests:** `LEAGUE_SHORT_NAMES` gains `N1: "Eredivisie"`, `B1: "Pro League"`, `T1: "Süper Lig"`, `G1: "Super League"`, `NOR: "Eliteserien"`, `AUT: "Bundesliga AT"`; `COMPETITION_ORDER` equals the site order in Global Constraints; `shortName("T1", "Süper Lig") === "Süper Lig"`.
- [ ] **Step 2:** types: `LeagueData.stats` becomes optional (goals-only files); `UpcomingMatch` gains optional `home_league?: string | null; away_league?: string | null`; add `UefaData` matching `uefa.json` above. Update doc comments.
- [ ] **Step 3: Run** `cd site && npm ci && npm test && npm run build` → pass (fix any type errors where `league.stats` is now optional by guarding, behaviour unchanged for full leagues).
- [ ] **Step 4: Commit** `feat(site): new league codes and optional stats in types`.

---

## Wave w15

### Task 4: goals-only-leagues (Python build + UEFA team leagues)

**Files:**
- Modify: `src/matchstats/build.py`, `src/matchstats/team_names.py`, `contract/data-contract.md`
- Test: `tests/matchstats/test_build.py`, `tests/matchstats/test_team_names.py`

**Interfaces:** Consumes Task 1 registry and Task 2 `load_goals_only`. Produces `leagues/NOR.json`, `leagues/AUT.json`, `h2h/NOR.json`, `h2h/AUT.json` and `home_league`/`away_league` on `upcoming`.

- [ ] **Step 1: Failing tests**
  - `test_goals_only_league_files`: stub goals-only loader → `leagues/NOR.json` has `goals`, `teams`, no `stats`; `season == "2026"`; `index.leagues` does **not** include NOR.
  - `test_goals_only_current_season_is_newest_in_file`: NOR rows for 2025 and 2026 only → teams/season stats come from 2026; goals model uses the newest 3 seasons present.
  - `test_goals_only_league_dropped_on_failure`: loader raises/returns `[]` → no NOR files, warning, build succeeds.
  - `test_uefa_rows_carry_team_leagues`: UCL `Galatasaray` (T1 team) vs `Bodø/Glimt` (NOR team) → `home_league "T1"`, `away_league "NOR"`, `league null`.
  - `test_uefa_ambiguous_name_has_null_league`: a name resolving in two leagues → that side `null`.
  - `test_uefa_unknown_team_null_league`: `Shakhtar` → `null`.
  - `test_league_rows_team_leagues_equal_code`: an E0 row has `home_league == away_league == "E0"`.
- [ ] **Step 2: Run** `uv run pytest -q` → fail.
- [ ] **Step 3: Implement** in `build.py`; validator checks goals-only files without `stats` (`_league_problems` gets the spec). Resolve UEFA names against all present `DATA_LEAGUES`.
- [ ] **Step 4: Aliases.** Resolve the names of the current UCL/UEL/UECL feeds against all 13 leagues (fetch the feeds); add aliases for teams of our leagues that do not resolve (e.g. `Bodø/Glimt`, `LASK`, `Salzburg`, `Sturm Graz`, `Fenerbahçe`, `PSV`, `Club Brugge`, `AEK Athens` if they fail). Test each alias target exists.
- [ ] **Step 5: Contract** text for goals-only files and `home_league`/`away_league`.
- [ ] **Step 6: Run** `uv run pytest -q` → pass; real build into a temp dir; report in `RESULT.md` how many UEFA rows in the window have both team leagues non-null.
- [ ] **Step 7: Commit** `feat(matchstats): norway and austria goals-only data and uefa team leagues`.

### Task 5: uefa-match-page (site, data only)

**Files:**
- Modify: `site/src/pages/match.astro`, `site/src/pages/index.astro`, `site/src/lib/calendar.ts`, `site/src/lib/render.ts`
- Test: `site/test/calendar.test.ts`, `site/test/render.test.ts`

**Interfaces:** Consumes Task 3 types. Produces `hasTeamData(match: UpcomingMatch): boolean` (true when `home_league` and `away_league` are both non-null strings) and `uefaMatchUrl(base: string, match: UpcomingMatch): string` in `calendar.ts`.

- [ ] **Step 1: Failing tests**
  - `hasTeamData` true for `{competition:"UCL", home_league:"SP1", away_league:"E0"}`, false when either is `null` or missing.
  - `uefaMatchUrl` builds `match?competition=UCL&home=Barcelona&home_league=SP1&away=Aston+Villa&away_league=E0` (URLSearchParams encoding).
  - Render: season comparison and last-6 rows of a goals-only team show "—" for xG, shots, corners, cards and never `NaN`; rows with no stat data at all hide the stat columns (builder's call which, test pins "no NaN" and "score and result shown").
- [ ] **Step 2: Run** `cd site && npm test` → fail.
- [ ] **Step 3: Implement.** Calendar: a UEFA row with `hasTeamData` and different leagues links to `uefaMatchUrl` (same-league UEFA rows keep the existing `league` link). Match page: when `competition` is present, load both league files, show header "Champions League" (competition name) with each team's league short name next to it, season comparison and last 6 from each team's own file, no head to head, no markets section yet (placeholder hidden). Missing file or team → existing error messages.
- [ ] **Step 4: Run** `cd site && npm ci && npm test && npm run build` → pass. Check at 360 px and in both themes.
- [ ] **Step 5: Commit** `feat(site): uefa match page with both teams' data`.

---

## Wave w16

### Task 6: uefa-strength (Python model + backtest + uefa.json)

**Files:**
- Create: `src/matchstats/uefa_strength.py`, `tests/matchstats/test_uefa_strength.py`, `tests/matchstats/fixtures/uefa_cl_sample.json`
- Modify: `src/matchstats/build.py`, `src/matchstats/cli.py`, `contract/data-contract.md`
- Test: `tests/matchstats/test_build.py`

**Interfaces:** Consumes registry, loaders, `fit_goals_model`, `parse_fixturedownload`, `resolve`. Produces:

```python
def uefa_result_urls(years: list[int]) -> dict[str, str]   # key f"{code}-{year}", e.g. "UCL-2025"
def fit_league_offsets(matches: list[UefaResult], domestic: dict[tuple[str, int], dict], l2: float) -> dict
    # -> {"home_advantage": float, "offsets": {code: {"attack": float, "defense": float}}}
def backtest(...) -> dict   # the "backtest" object of uefa.json
```

`UefaResult` is a frozen dataclass: `year, kickoff_utc, home, away, home_goals, away_goals, home_league, away_league`. `domestic[(code, year)]` is that league's `goals` object fitted on its matches up to that UEFA season's start (cache per key; past seasons never change).

- [ ] **Step 1: Failing tests**
  - `test_offsets_recover_synthetic_strength`: synthetic two-league world where league B teams score 30% less against league A → fitted `offsets` make A stronger (sign check and magnitude within 0.1 of truth on log scale); reference league `E0` offsets are exactly 0.
  - `test_l2_keeps_sparse_league_near_zero`: a league with 2 matches has |offsets| < 0.05.
  - `test_same_league_uefa_matches_ignored_or_neutral`: E0 vs E0 rows do not move offsets.
  - `test_backtest_reports_three_log_losses`: keys `held_out, matches, log_loss, log_loss_unadjusted, log_loss_baseline`.
  - `test_build_writes_uefa_json`: stubbed feeds → `uefa.json` matches the schema above; `calibrated` true iff `log_loss < log_loss_unadjusted`.
  - `test_build_keeps_previous_uefa_json_when_feeds_fail`: previous `out/uefa.json` exists and past feeds fail → identical file in the new output.
  - `test_build_without_previous_uefa_json_and_failed_feeds`: no `uefa.json`, build succeeds.
- [ ] **Step 2: Run** `uv run pytest -q` → fail.
- [ ] **Step 3: Implement.** Fit by maximum likelihood (Poisson with Dixon-Coles tau, as `goals_model.py`) over offsets + `home_advantage` with an L2 penalty on offsets; `E0` fixed at 0. Teams that do not resolve uniquely to a league with domestic params are dropped. Choose the variant (separate attack/defense, or `attack = s`, `defense = -s`) and `l2`/season count by the held-out backtest; write the choice and the numbers in `RESULT.md`.
- [ ] **Step 4: CLI** `uv run matchstats uefa-backtest` prints the backtest object and the offsets table.
- [ ] **Step 5: Contract** section for `uefa.json`.
- [ ] **Step 6: Run** `uv run pytest -q` → pass; run `uv run matchstats uefa-backtest` against real feeds and paste the output into `RESULT.md`.
- [ ] **Step 7: Commit** `feat(matchstats): uefa league strength model`.

### Task 7: cross-league-markets (site)

**Files:**
- Modify: `site/src/lib/markets.ts`, `site/src/lib/data.ts`, `site/src/pages/match.astro`, `site/src/pages/index.astro`
- Test: `site/test/markets.test.ts`

**Interfaces:** Consumes `UefaData` (Task 3), Task 5 page and `hasTeamData`. Produces `crossLeagueMarkets(home: {name: string; league: LeagueData; code: string}, away: {…}, uefa: UefaData): Market[]` and `loadUefa(): Promise<UefaData | null>` (null on 404 or invalid JSON).

- [ ] **Step 1: Failing tests**
  - Goal markets use the cross-league formula above: with all offsets 0, `home_advantage` equal to the home league's and both teams in the same league data, the 1X2 equals `matchMarkets` of that league (tolerance 1e-9).
  - A positive `offsets[LH].attack` raises home win probability.
  - Stat markets: expected home corners `= sqrt(LH.avg_home * LA.avg_home) * H.home_for * A.away_against`; away side symmetrical with `avg_away`.
  - Either league without `stats` → no corners/shots/cards markets, goal markets present.
  - `uefa.calibrated === false`, missing league in `offsets`, or `loadUefa()` → `null` → the page/calendar get no markets (test the pure decision function `crossLeagueAvailable(uefa, homeCode, awayCode): boolean`).
- [ ] **Step 2: Run** `cd site && npm test` → fail.
- [ ] **Step 3: Implement.** Match page UEFA mode shows the markets section; under the corners/shots/cards groups the note: "Córners, tiros y tarjetas salen de los números de cada equipo en su liga, sin ajuste por nivel de liga." Calendar UEFA rows with `hasTeamData` show the 1X2 probabilities like league rows.
- [ ] **Step 4: Run** `cd site && npm ci && npm test && npm run build` → pass.
- [ ] **Step 5: Commit** `feat(site): cross-league market probabilities for uefa matches`.

### Gate (orchestrator, after w16 merges)

Run `uv run matchstats uefa-backtest`. If `log_loss` does not beat `log_loss_unadjusted`, stop and report to the user before pushing (the site already hides probabilities when `calibrated` is false).
