# Task 6: site-pages

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `site/src/lib/markets.ts`
- `site/src/lib/render.ts`
- `site/src/lib/data.ts`
- `site/src/pages/**`
- `site/src/styles/**`
- `site/scripts/**`
- `site/package.json`
- `site/package-lock.json`
- `site/test/markets.test.ts`
- `site/test/render.test.ts`

## Test command (must pass before you finish)

`cd site && npm test && npm run build`

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
