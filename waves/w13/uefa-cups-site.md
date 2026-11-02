# Task: uefa-cups-site

User request (2026-11-02, verbatim): "ahora agrega champions, europa league y conference league" — the home calendar must show UEFA Champions League, Europa League and Conference League matches with their own filter chips.

A parallel task adds them to the data: `index.json` → `upcoming` items will carry `competition` codes `UCL`, `UEL`, `UECL` with `competition_name` `"Champions League"`, `"Europa League"`, `"Conference League"`. Most of these matches have `league: null` (teams from different leagues): the site already lists such matches without probabilities or analysis link, exactly like DFB-Pokal matches. Do not change that behavior.

## Allowed files

- `site/src/lib/leagues.ts`
- `site/src/lib/types.ts`
- `site/test/leagues.test.ts`
- `site/test/calendar.test.ts`

## Change (TDD: failing tests first)

1. `leagues.ts`:
   - `LEAGUE_SHORT_NAMES` gains `UCL: "Champions"`, `UEL: "Europa League"`, `UECL: "Conference"`.
   - `COMPETITION_ORDER` becomes `["E0", "SP1", "I1", "D1", "F1", "E1", "P1", "UCL", "UEL", "UECL", "DFB"]`.
   - Update the doc comment of `COMPETITION_ORDER` (leagues, then UEFA cups, then the DFB-Pokal).
2. `types.ts`: the `UpcomingMatch` doc comment lists the new codes.
3. Tests:
   - `leagues.test.ts`: update the expected short names and order; `shortName("UCL", "Champions League")` is `"Champions"`.
   - `calendar.test.ts`: `competitionsOf` on matches of `DFB`, `UECL`, `E0`, `UCL`, `UEL` returns `["E0", "UCL", "UEL", "UECL", "DFB"]`; `filterByCompetitions` with `{"UCL", "E0"}` keeps both competitions' matches only; a `UCL` match with `league: null` is not analyzable (`isAnalyzable` false).

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
