# More Leagues, Collapsible Comparator and Calendar Filters Plan

> Executed through `orchestrate-waves`. Each worker reads this whole file plus `contract/data-contract.md`.

**User request (2026-10-30, verbatim):**
1. "que la parte de elegir equipos para comparar sea un desplegable" — confirmed meaning: the whole comparator block collapses, **closed by default** behind a "Comparar equipos" button, so the calendar is on top when the page opens.
2. "filtro de ligas para el calendario y que se puedan agrupar por ligas o solo ordenar por hora independientemente de la liga"
3. "agregar mas ligas, empieza por la championship de inglaterra y por la liga portuguesa"

Existing rules still apply: Spanish copy, design tokens and rules from `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` (read its Global constraints), craft floor `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`.

## New leagues (verified 2026-10-30)

- football-data season files: `E1` (Championship, full stats + xG) and `P1` (Primeira Liga, full stats + xG). Portugal has no second division in football-data.
- fixturedownload slugs: `championship-2026` (E1) and `primeira-liga-2026` (P1).
- League order everywhere: `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1, `E1` Championship, `P1` Primeira Liga.
- **Head to head** now uses every loaded division of the league's country, because teams move between them: England `E0`, `E1`, `E2` (League One); Spain `SP1`, `SP2`; Italy `I1`, `I2`; Germany `D1`, `D2`; France `F1`, `F2`; Portugal `P1`. Replace `SECOND_DIVISION` with `COUNTRY_DIVISIONS: dict[str, tuple[str, ...]]` (league → its country's divisions, top first) and update every use.
- A cup match gets `league` when both teams are in the same one of the 7 leagues (e.g. a DFB-Pokal tie stays D1-only; nothing else changes).
- Validation: `index.json.leagues` equals the 7 codes in order; each league ≥ 16 teams (E1 has 24, P1 18).

## Contract change

`index.json.leagues` lists 7 leagues in the order above. Nothing else changes shape. Update `contract/data-contract.md` (league list, head-to-head divisions) and add one `E1` entry to `contract/example/index.json` `leagues` (3 Championship team names are enough; keep it consistent with the doc; the example `leagues/` and `h2h/` files for E0 stay as they are).

---

## Wave 10 (parallel)

### Task F: `leagues-e1-p1` (Python + contract)

**Files:** `src/matchstats/leagues.py`, `src/matchstats/fixture_sources.py`, `src/matchstats/team_names.py`, `src/matchstats/build.py`, `src/matchstats/backtest.py` (only if it uses `SECOND_DIVISION`), `tests/matchstats/test_leagues.py`, `tests/matchstats/test_fixture_sources.py`, `tests/matchstats/test_team_names.py`, `tests/matchstats/test_build.py`, `tests/matchstats/fixtures/fd_championship-2026_sample.json`, `tests/matchstats/fixtures/fd_primeira-liga-2026_sample.json`, `tests/matchstats/fixtures/teams_2627.json`, `contract/data-contract.md`, `contract/example/index.json`.

- [ ] Record samples of the two real fixturedownload feeds and add the current E1 and P1 team names to `teams_2627.json` (from the real 2026/27 football-data files; download `E1`/`P1` 2627 if not cached in `/mnt/data/projects/analisis/data/raw/2627/`).
- [ ] Failing tests: `TOP_LEAGUES` order and names; `COUNTRY_DIVISIONS` values exactly as above; `league_fixture_urls("2627")` has the 7 slugs; **every team in the recorded E1 and P1 feeds resolves** to a current football-data name (add verified aliases only); build writes `leagues/E1.json`, `leagues/P1.json`, `h2h/E1.json`, `h2h/P1.json` and includes them in `index.json`; an E0 head to head includes a meeting played in `E1` and an E1 head to head includes one played in `E0`; validation requires the 7 leagues.
- [ ] Implement, update the contract doc and example.
- [ ] `uv run pytest -q` → PASS. Commit `feat(matchstats): add championship and primeira liga`.

### Task G: `home-collapse-filters` (site)

**Files:** `site/src/pages/index.astro`, `site/src/lib/calendar.ts`, `site/src/lib/leagues.ts` (new), `site/test/calendar.test.ts`, `site/test/leagues.test.ts` (new).

`leagues.ts`: `LEAGUE_SHORT_NAMES: Record<string, string>` = `E0 "Premier"`, `SP1 "LaLiga"`, `I1 "Serie A"`, `D1 "Bundesliga"`, `F1 "Ligue 1"`, `E1 "Championship"`, `P1 "Liga Portugal"`, `DFB "DFB-Pokal"`; `shortName(code: string, fallback: string): string`. Use it everywhere the page shows a short competition name. Leagues for the comparator come from `index.json.leagues` (never a hard-coded list of 5).

**Comparator (request 1):** the whole block (league, Local, Visitante, Analizar) sits inside a collapsible panel, **closed by default**, opened by a full-width button `Comparar equipos` with a chevron (`Icon` `chevron-left` rotated, or add `chevron-down` to `Icon.astro` only if needed — then add `site/src/components/Icon.astro` to your files) and `aria-expanded`/`aria-controls`. The league picker becomes a `<select>` (7 leagues do not fit as chips at 360 px). Expand/collapse animates height or opacity in ≤ 200 ms and respects `prefers-reduced-motion`. The calendar is the first content below the header.

**Calendar (request 2):**
- League filter: a horizontally scrollable chip row (the row scrolls, never the page) with `Todas` plus one chip per competition **present in the day's matches** (short names), multi-select: selecting chips narrows the list; `Todas` clears the selection. Chips are toggle buttons with `aria-pressed`.
- Order toggle: segmented control `Por hora` / `Por liga`. `Por hora`: one list sorted by kickoff regardless of league (current behavior). `Por liga`: one group per competition in the league order above then `DFB-Pokal`, each with a small heading (competition name and match count, e.g. `Serie A · 3`), matches sorted by kickoff inside.
- Default: `Todas` and `Por hora`. Remember both choices in `localStorage` (`ms-cal-leagues`, `ms-cal-order`), wrapped in try/catch.
- Empty result after filtering: `No hay partidos de estas ligas este día.` with a `Ver todas` button that resets the filter.
- Pure helpers in `calendar.ts` (tested): `competitionsOf(matches): string[]` (in league order, then DFB), `filterByCompetitions(matches, selected: Set<string>): UpcomingMatch[]` (empty set = all), `groupByCompetition(matches): { competition: string; matches: UpcomingMatch[] }[]` (league order, kickoff inside).

- [ ] Failing tests for `leagues.ts` and the three helpers first (watch them fail), then implement.
- [ ] `cd site && npm ci && npm test && npm run build` → PASS. Commit `feat(site): collapsible comparator and calendar filters`.
