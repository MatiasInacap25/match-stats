# Task: goals-only-leagues

Spec: `docs/superpowers/specs/2026-11-02-uefa-cross-league-design.md`
Plan: `docs/superpowers/plans/2026-11-02-uefa-cross-league.md` (this is its Task 4, copied verbatim below with the plan's global sections). Another task of this wave runs in parallel on other files; do not touch files outside the list.

## Allowed files

- `src/matchstats/build.py`
- `src/matchstats/team_names.py`
- `contract/data-contract.md`
- `tests/matchstats/test_build.py`
- `tests/matchstats/test_team_names.py`

## Test command (must pass before you finish)

`uv run pytest -q`

## Notes from the orchestrator (wave w14 is merged into the base)

- The registry is in `src/matchstats/leagues.py` (`LEAGUES`, `SITE_LEAGUES`, `DATA_LEAGUES`); `NOR`/`AUT` are declared there and currently skipped by `build.py`. Optional site leagues are already built one at a time and dropped on failure (`_optional_matches` / `_cached_matches` in `build.py`): follow that pattern for NOR/AUT.
- `load_goals_only(country, div, cache_dir)` in `ingest.py` already falls back to the cached copy and returns `[]` when there is no usable data. `Match` stat fields are `int | None`; `team_stats` handles `None`. `stat_model.py` must not be called for goals-only leagues.

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

