# Task 9: nightly-deploy

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files. Never commit files outside them.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `.github/workflows/nightly.yml`
- `site/vercel.json`
- `README.md`
- `tests/test_workflow.py`

## Test command (must pass before you finish)

`uv run pytest -q`

## Notes from earlier waves (binding)

- Match.season holds the season code (e.g. "2627"); use leagues.season_label() for the JSON 'season' field ("2026/27").
- Existing signatures: fit_goals_model(matches, ref_date, xi=0.002, l2=0.1) -> dict (raises ValueError on empty input); fit_stat_model(matches, stat, current_season, shrink=5.0) -> dict (raises ValueError on empty input or unknown stat); STAT_FIELDS in stat_model; league_table(matches); season_stats(matches, team, table); last_matches(matches, team, n=6); pair_key(a, b); head_to_head(matches, a, b); load_matches(divs, seasons, cache_dir, current_season); download(url, cache_file, refresh) -> str | None; parse_fixtures_csv(text); FIXTURES_URL; season_code(d); season_label(code); recent_seasons(current, n); TOP_LEAGUES; SECOND_DIVISION.
- fit_stat_model only returns teams that appear in the matches it gets; season_stats returns position/points None for a team missing from the table. The build must pass the right matches so every current-season team is present; validate_output catches gaps.
- Contract: when a season side has matches == 0, its per-match averages and *_pct are null.
- site/public/data/ is written by the build and committed only by the nightly job. Tests must write to tmp_path, never into site/public/data.
- Python: uv run pytest -q runs everything.

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
