# Calendar Sources and Cup Matches Plan

> Executed through `orchestrate-waves`. Each worker reads this whole file plus `contract/data-contract.md`.

**Goal:** The Hoy / Mañana calendar shows every top-5 league match (football-data's `fixtures.csv` lags several days) plus DFB-Pokal matches. Cup matches get probabilities and an analysis link only when both teams are in the same top-5 league's data; otherwise they are listed without them.

**User decisions (2026-10-27):** "para mañana debían aparecer partidos de la Serie A y hay partidos de copa en España, Alemania e Inglaterra" → approved: cup matches shown, analysis only when both teams are from the same league, the rest only listed. Copa del Rey and Carabao Cup have no free keyless source (checked fixturedownload, openfootball, OpenLigaDB, ESPN): **out of scope** until the user gets a free API-Football key.

## Sources (verified 2026-10-27)

- **League fixtures:** `https://fixturedownload.com/feed/json/<slug>` with slugs `epl-2026` (E0), `la-liga-2026` (SP1), `serie-a-2026` (I1), `bundesliga-2026` (D1), `ligue-1-2026` (F1). `2026` = season 2026/27; derive it from `season_code` (`"2627"` → `2026`). JSON list of objects with `DateUtc` (`"2026-10-27 17:30:00Z"`), `HomeTeam`, `AwayTeam`, `HomeTeamScore`, `AwayTeamScore`, `RoundNumber`.
- **DFB-Pokal:** `https://api.openligadb.de/getmatchdata/dfb/<year>` (same `2026`). JSON list with `matchDateTime` (German local time, no offset → convert from `Europe/Berlin` to UTC), `team1.teamName`, `team2.teamName`.
- Download with the existing `download()` (cache under `<cache>/fixtures/<name>.json`, `refresh=True`), polite pauses as today. A failed or 404 source is skipped with a warning; it never fails the build.
- `football-data` `fixtures.csv` stays as a fallback for leagues whose fixturedownload feed failed.

## Team names

The data uses football-data names (e.g. `Man United`, `Ein Frankfurt`, `Hamburg`, `Milan`). Fixture sources use others (`Man Utd`, `Eintracht Frankfurt`, `Hamburger SV`, `AC Milan`…). Add `src/matchstats/team_names.py`:

- `normalize(name: str) -> str` — lowercase, strip accents, drop tokens `fc`, `cf`, `afc`, `sc`, `sv`, `vfl`, `vfb`, `tsg`, `1.`, `ac`, `as`, `ssc`, `us`, `rc`, `ca`, `cd`, `ud`, `rcd`, `og`, `stade`, `de`, `the`, punctuation and digits-only tokens.
- `ALIASES: dict[str, str]` — explicit source-name → football-data-name overrides for cases normalization cannot solve (start from the real feeds: e.g. `Man Utd` → `Man United`, `Wolves` → `Wolves`, `Spurs` → `Tottenham`, `Nott'm Forest`/`Nottingham Forest` → `Nott'm Forest`, `Eintracht Frankfurt` → `Ein Frankfurt`, `Borussia Mönchengladbach` → `M'gladbach`, `Bayer 04 Leverkusen` → `Leverkusen`, `Hamburger SV` → `Hamburg`, `1. FC Köln` → `FC Koln`, `Athletic Club` → `Ath Bilbao`, `Atlético de Madrid`/`Atletico Madrid` → `Ath Madrid`, `Paris Saint-Germain` → `Paris SG`, `Internazionale`/`Inter` → `Inter`, `AC Milan` → `Milan`). Verify every alias against the real football-data team list of the current season; never guess one.
- `resolve(name: str, known: set[str]) -> str | None` — alias first, then a unique normalized match among `known`, else `None`.

**Acceptance:** for every top-5 league, every team in the current fixturedownload feed resolves to a current-season football-data team (test against recorded feeds saved as fixtures in `tests/matchstats/fixtures/`). A cup team that does not resolve is fine (lower divisions).

## Contract change (`index.json.upcoming`)

Each item becomes:

```json
{"competition": "I1", "competition_name": "Serie A", "kickoff_utc": "2026-10-27T17:30:00Z",
 "home": "Sassuolo", "away": "Lazio", "league": "I1"}
```

- `competition`: league code for league matches; `"DFB"` with `competition_name` `"DFB-Pokal"` for the cup.
- `home`/`away`: football-data names when resolved, else the source name.
- `league`: the top-5 league code whose data has **both** teams (for league matches, the league itself); `null` when no single league has both. The site offers probabilities and the analysis link only when `league` is not `null`.
- Window unchanged: Madrid dates today − 1 … today + 2. Sorted by kickoff, then competition order (E0, SP1, I1, D1, F1, DFB), then home.
- `today` (legacy) unchanged.

---

## Wave 9 (parallel)

### Task D: `fixture-sources` (Python + contract)

**Files:** `src/matchstats/team_names.py`, `src/matchstats/fixture_sources.py`, `src/matchstats/build.py`, `tests/matchstats/test_team_names.py`, `tests/matchstats/test_fixture_sources.py`, `tests/matchstats/test_build.py`, `tests/matchstats/fixtures/fd_serie-a-2026_sample.json`, `tests/matchstats/fixtures/fd_bundesliga-2026_sample.json`, `tests/matchstats/fixtures/openligadb_dfb_2026_sample.json`, `tests/matchstats/fixtures/teams_2627.json`, `contract/data-contract.md`, `contract/example/index.json`.

`fixture_sources.py`: `league_fixture_urls(season: str) -> dict[str, str]`, `cup_fixture_urls(season: str) -> dict[str, str]` (`{"DFB": ...}`), `parse_fixturedownload(text: str, competition: str) -> list[UpcomingFixture]`, `parse_openligadb(text: str, competition: str) -> list[UpcomingFixture]` with `@dataclass(frozen=True) UpcomingFixture: competition: str; kickoff_utc: datetime; home: str; away: str`.

- [ ] Record samples from the real feeds (a few rounds each, incl. 2026-10-27/28) and the current football-data team names per league (`teams_2627.json`, from the cached season CSVs).
- [ ] Failing tests: parsers (UTC parsing; Berlin → UTC for OpenLigaDB incl. a summer-time date), `resolve` (aliases, normalized unique match, ambiguous → `None`), **every team in the recorded league samples resolves**, build `upcoming` with the new fields (league match `league` = itself; DFB `Hamburger SV–Eintracht Frankfurt` → `Hamburg`/`Ein Frankfurt`, `league: "D1"`; `SG Sonnenhof Großaspach–FC Augsburg` → `league: null`, home kept as source name), a failing source is skipped and the rest still builds, fallback to football-data `fixtures.csv` for a league whose feed failed.
- [ ] Implement; update the contract doc and `contract/example/index.json` (`upcoming` items with the new fields, one `league: null` cup example).
- [ ] `uv run pytest -q` → PASS. Commit `feat(matchstats): full league fixtures and DFB-Pokal in upcoming`.

### Task E: `calendar-cups-ui` (site)

**Files:** `site/src/lib/types.ts`, `site/src/lib/calendar.ts`, `site/src/pages/index.astro`, `site/test/calendar.test.ts`.

- `UpcomingMatch` becomes `{ competition: string; competition_name: string; kickoff_utc: string; home: string; away: string; league: string | null }`.
- Calendar rows show `competition_name` (short league names as today for the 5 leagues; `DFB-Pokal` for the cup) and keep kickoff in local time.
- `league !== null` → probabilities (`1`, `Más de 2.5`) and a link to `/match?league=<league>&home=…&away=…`. `league === null` → no probabilities, not a link, and a muted note `Sin análisis: equipos de distintas categorías.`
- Optional filter is **not** needed; keep the list sorted as delivered.
- [ ] Failing tests on the example data first (`calendar.test.ts`: grouping still by local day with the new shape; a helper `isAnalyzable(match)`), then implement. Spanish copy, existing design tokens and rules (`/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`).
- [ ] `cd site && npm ci && npm test && npm run build` → PASS. Commit `feat(site): show cup matches in the calendar`.
