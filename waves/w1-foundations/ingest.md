# Task 1: ingest

You are implementing one task of a larger plan. Other workers implement other tasks in parallel; stay inside your allowed files.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1)
- Plan: `docs/superpowers/plans/2026-10-26-match-stats-site.md`
- Data contract (binding): `contract/data-contract.md` and `contract/example/`

Read the contract before starting.

## Allowed files

- `pyproject.toml`
- `uv.lock`
- `.gitignore`
- `src/matchstats/**`
- `tests/matchstats/**`

## Test command (must pass before you finish)

`uv run pytest -q`

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

### Task 1: `ingest` — leagues, match model, CSV download and parsing (Wave 1)

**Files:**
- Modify: `pyproject.toml` (add `src/matchstats` to `[tool.hatch.build.targets.wheel] packages`; dependencies `numpy>=2`, `scipy>=1.14`), `uv.lock`, `.gitignore` (add `data/raw/`)
- Create: `src/matchstats/__init__.py`, `src/matchstats/leagues.py`, `src/matchstats/match.py`, `src/matchstats/ingest.py`
- Test: `tests/matchstats/test_leagues.py`, `tests/matchstats/test_ingest.py`, `tests/matchstats/fixtures/E0_2627_sample.csv`, `tests/matchstats/fixtures/fixtures_sample.csv`

**Interfaces — Produces:**
- `leagues.py`: `TOP_LEAGUES: dict[str, str]` (code → name, in the Global Constraints order), `SECOND_DIVISION: dict[str, str]` (`{"E0": "E1", "SP1": "SP2", "I1": "I2", "D1": "D2", "F1": "F2"}`), `season_code(d: date) -> str`, `season_label(code: str) -> str` (`"2627"` → `"2026/27"`), `recent_seasons(current: str, n: int) -> list[str]` (newest first, includes current).
- `match.py`: `@dataclass(frozen=True) class Match` with fields `div: str, season: str, date: date, home: str, away: str, home_goals: int, away_goals: int, home_xg: float | None, away_xg: float | None, home_shots: int, away_shots: int, home_sot: int, away_sot: int, home_corners: int, away_corners: int, home_yellow: int, away_yellow: int, home_red: int, away_red: int` and properties `home_cards`/`away_cards` (`yellow + 2 * red`). `@dataclass(frozen=True) class Fixture: div: str, date: date, time: str, home: str, away: str`.
- `ingest.py`: `season_url(code: str, div: str) -> str`, `FIXTURES_URL: str`, `parse_season_csv(text: str, div: str, season: str) -> list[Match]`, `parse_fixtures_csv(text: str) -> list[Fixture]`, `download(url: str, cache_file: Path, refresh: bool) -> str | None` (returns `None` on HTTP 404), `load_matches(divs: list[str], seasons: list[str], cache_dir: Path, current_season: str) -> list[Match]`, `class IngestError(RuntimeError)`.

- [ ] **Step 1: Capture fixtures.** Download the real `E0` 2026/27 file and `fixtures.csv` (follow redirects). Save the header plus 5 data rows of each as the two fixture files. Add one extra row to the season sample with empty `HxG`/`AxG`, and one with an empty `FTHG` (a postponed match).
- [ ] **Step 2: Write failing tests:**
  - `test_season_code_boundaries` — `season_code(date(2026, 6, 30)) == "2526"`, `season_code(date(2026, 7, 1)) == "2627"`; `season_label("2627") == "2026/27"`; `recent_seasons("2627", 3) == ["2627", "2526", "2425"]`.
  - `test_parse_season_csv_real_sample` — the 5 real rows parse; the first row's teams, goals, `HS/HST/HC/HY/HR` equal the CSV values; `date` is a `datetime.date`.
  - `test_cards_are_points` — a match with 2 yellow + 1 red home has `home_cards == 4`.
  - `test_missing_xg_is_none` — the empty-xG row gives `home_xg is None`.
  - `test_skips_rows_without_result` — the empty `FTHG` row is not returned.
  - `test_two_digit_year` — `"25/10/26"` parses to `date(2026, 10, 25)`.
  - `test_parse_fixtures` — the sample returns `Fixture` objects with the right `div`, `date`, `time`, `home`, `away`.
  - `test_download_uses_cache_unless_refresh` — monkeypatch `urllib.request.urlopen`: an existing cache file with `refresh=False` → no network call; `refresh=True` → one call, and the cache file is rewritten.
  - `test_download_404_returns_none`, and `test_load_matches_skips_missing_season` — a 404 for one season is skipped; the others load.
  - `test_download_retries_then_raises` — 3 failed attempts (non-404 error) → `IngestError`.
- [ ] **Step 3:** Run `uv run pytest tests/matchstats -q` → FAIL.
- [ ] **Step 4:** Implement. `download`: `urllib.request` (follows redirects), header `User-Agent: matchstats/0.1`, timeout 30 s, 3 attempts with 2 s back-off, 1 s pause after every network call (be polite to the free site), write the cache file only after a successful read. `load_matches` refreshes only files of `current_season` and caches the rest under `cache_dir/<season>/<div>.csv`. Decode with `utf-8-sig`.
- [ ] **Step 5:** Run `uv run pytest -q` → all PASS (orchestra tests included).
- [ ] **Step 6:** Commit `feat(matchstats): ingest football-data CSVs`.

---
