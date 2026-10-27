# Task 2: site-core

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `site/**`

## Test command (must pass before you finish)

`cd site && npm test && npm run build`

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
