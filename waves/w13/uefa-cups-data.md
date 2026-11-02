# Task: uefa-cups-data

User request (2026-11-02, verbatim): "ahora agrega champions, europa league y conference league" — add UEFA Champions League, Europa League and Conference League matches to the home calendar (`index.json` → `upcoming`).

Context: `docs/superpowers/plans/2026-10-27-calendar-sources-cups.md` (how the DFB-Pokal was added; follow the same pattern) and `contract/data-contract.md`.

## Allowed files

- `src/matchstats/fixture_sources.py`
- `src/matchstats/build.py`
- `src/matchstats/team_names.py`
- `tests/matchstats/test_fixture_sources.py`
- `tests/matchstats/test_build.py`
- `contract/data-contract.md`

## Facts (verified 2026-11-02)

- fixturedownload has the three feeds, same JSON shape as the league feeds (`DateUtc`, `HomeTeam`, `AwayTeam`), so `parse_fixturedownload` reads them unchanged:
  - `https://fixturedownload.com/feed/json/champions-league-2026`
  - `https://fixturedownload.com/feed/json/europa-league-2026`
  - `https://fixturedownload.com/feed/json/conference-league-2026`
- Sample row: `{"MatchNumber":129,"RoundNumber":4,"DateUtc":"2026-11-03 20:00:00Z","Location":"Camp Nou","HomeTeam":"Barcelona","AwayTeam":"Aston Villa","Group":null,"HomeTeamScore":null,"AwayTeamScore":null,"Winner":""}`
- Feed names that do not resolve today against current football-data names, and must:
  `"Atleti"` → `"Ath Madrid"`, `"B. Dortmund"` → `"Dortmund"`, `"Bayern München"` → `"Bayern Munich"`, `"Leipzig"` → `"RB Leipzig"`, `"Braga"` → `"Sp Braga"`.
- `"Paris"` (Paris Saint-Germain in the UEFA feeds) currently resolves **wrongly** to `"Paris FC"` by normalization. It must map to `"Paris SG"`. The Ligue 1 feed uses `"Paris FC"` and `"Paris Saint-Germain"`, never `"Paris"`, so an alias is safe.

## Change (TDD: failing tests first)

1. `fixture_sources.py`: competition codes and slugs `UCL` → `champions-league`, `UEL` → `europa-league`, `UECL` → `conference-league`; a function `uefa_fixture_urls(season)` returning `{code: url}` for the three, built like `league_fixture_urls` (season year 2026 for `"2627"`).
2. `build.py`:
   - `COMPETITION_NAMES` gains `UCL: "Champions League"`, `UEL: "Europa League"`, `UECL: "Conference League"`. Competition order: the 7 leagues, then `UCL`, `UEL`, `UECL`, then `DFB`.
   - `_upcoming_fixtures` reads the three UEFA feeds with `parse_fixturedownload`. Like the DFB-Pokal: a failed or missing UEFA feed is skipped with a warning naming the code; no `fixtures.csv` fallback; never fails the build.
   - UEFA matches use the existing non-league path in `_upcoming_entry`: `league` is the one top league whose current teams include both sides, else `null`; team names are resolved to football-data names when possible, else kept as in the feed.
   - Update the `_upcoming_fixtures` docstring.
3. `team_names.py`: add the six aliases above under a `# UEFA competitions` comment.
4. `contract/data-contract.md`: `upcoming` now also lists UCL/UEL/UECL matches; update the competition list, `competition_name` values, the sort order `(E0, SP1, I1, D1, F1, E1, P1, UCL, UEL, UECL, DFB)`, the `league` rule (same as DFB-Pokal) and the Sources line.

## Tests to add

- `uefa_fixture_urls("2627")` returns exactly the three URLs above.
- A UCL feed row between teams of two different top leagues (e.g. `"Barcelona"` vs `"Aston Villa"` with synthetic teams) appears in `upcoming` with `competition: "UCL"`, `competition_name: "Champions League"`, `kickoff_utc` in UTC, football-data names, and `league: null`.
- A UEL row between two teams of the same top league gets that league.
- `"Paris"` resolves to `"Paris SG"` (and `"Paris FC"` still resolves to `"Paris FC"`); each new alias resolves to its target.
- A failing UECL feed is skipped with a warning containing `UECL` while league rows still build.
- Sorting: rows at the same kickoff follow the order leagues → UCL → UEL → UECL → DFB.
- Existing tests keep passing unchanged (DFB-Pokal and league behavior must not change).

## Test command (must pass before you finish)

`uv run pytest -q`
