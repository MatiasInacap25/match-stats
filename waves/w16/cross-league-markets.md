# Task: cross-league-markets

Spec: `docs/superpowers/specs/2026-11-02-uefa-cross-league-design.md`
Plan: `docs/superpowers/plans/2026-11-02-uefa-cross-league.md` (this is its Task 7, copied verbatim below with the plan's global sections). Another task of this wave runs in parallel on other files; do not touch files outside the list.

## Allowed files

- `site/src/lib/markets.ts`
- `site/src/lib/data.ts`
- `site/src/lib/types.ts`
- `site/src/pages/match.astro`
- `site/src/pages/index.astro`
- `site/test/markets.test.ts`
- `site/test/render.test.ts`

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`

## Notes from the orchestrator (waves w14 and w15 are merged into the base)

- `site/src/pages/match.astro` has a `mainUefa` path (cross-league UEFA page, data only) and `site/src/lib/calendar.ts` has `hasTeamData`, `isCrossLeagueUefa`, `uefaMatchUrl`. Calendar rows for cross-league UEFA matches link to the page but show no probabilities yet.
- Follow-up from wave w15: `LastMatch` stat fields in `site/src/lib/types.ts` are typed `number` but are `null` for goals-only teams; widen them to `number | null` and remove the `as unknown as LastMatch` cast in `site/test/render.test.ts`.
- A parallel task writes `uefa.json`; the local data has none yet, so test with fixtures.

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

