# Task: uefa-strength

Spec: `docs/superpowers/specs/2026-11-02-uefa-cross-league-design.md`
Plan: `docs/superpowers/plans/2026-11-02-uefa-cross-league.md` (this is its Task 6, copied verbatim below with the plan's global sections). Another task of this wave runs in parallel on other files; do not touch files outside the list.

## Allowed files

- `src/matchstats/uefa_strength.py`
- `src/matchstats/build.py`
- `src/matchstats/cli.py`
- `contract/data-contract.md`
- `tests/matchstats/test_uefa_strength.py`
- `tests/matchstats/test_build.py`
- `tests/matchstats/fixtures/uefa_cl_sample.json`

## Test command (must pass before you finish)

`uv run pytest -q`

## Notes from the orchestrator (waves w14 and w15 are merged into the base)

- Registry: `src/matchstats/leagues.py` (`LEAGUES`, `DATA_LEAGUES`). Domestic data: `load_matches` (full leagues, `mmz4281`) and `load_goals_only` (NOR/AUT). Goals-only seasons: NOR uses calendar years (`"2026"`), AUT football-data codes (`"2627"`); see `CALENDAR_SEASON_LEAGUES` in `build.py`.
- UEFA team-name resolution against all leagues already exists in `build.py` (`home_league`/`away_league` on `upcoming`); reuse it for past UEFA results instead of writing a second resolver.
- Past UEFA feeds verified: `champions-league-2025`, `europa-league-2025`, `conference-league-2025`, `champions-league-2024` return complete results (`HomeTeamScore`/`AwayTeamScore`).
- A real build with a cold cache takes about 9 minutes. Do not wait on a background job with a monitor and then go idle: run long commands in the foreground (timeout up to 10 minutes) and finish the task in the same turn.

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

