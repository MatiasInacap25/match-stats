# Task: league-registry

Spec: `docs/superpowers/specs/2026-11-02-uefa-cross-league-design.md`
Plan: `docs/superpowers/plans/2026-11-02-uefa-cross-league.md` (this is its Task 1, copied verbatim below with the plan's global sections). Other tasks of this wave run in parallel on other files; do not touch files outside the list.

## Allowed files

- `src/matchstats/leagues.py`
- `src/matchstats/build.py`
- `src/matchstats/fixture_sources.py`
- `src/matchstats/team_names.py`
- `contract/data-contract.md`
- `tests/matchstats/test_build.py`
- `tests/matchstats/test_leagues.py`
- `tests/matchstats/test_fixture_sources.py`
- `tests/matchstats/test_team_names.py`

## Test command (must pass before you finish)

`uv run pytest -q`

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

