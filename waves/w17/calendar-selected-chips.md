# Task: calendar-selected-chips

User report (2026-11-02, verbatim): "en local no me salen los partidos". Confirmed fix (verbatim): "si, lanza el arreglo".

## Bug (reproduced by the orchestrator)

The calendar remembers the league filter in `localStorage` (`ms-cal-leagues`). With `["UCL"]` saved and no Champions League match on the selected day, the chip row shows only the competitions of that day (Champions is absent), "Todas" is not pressed, and the list shows "No hay partidos de estas ligas este día." The user cannot see which filter is active nor untoggle it.

## Allowed files

- `site/src/lib/calendar.ts`
- `site/src/pages/index.astro`
- `site/test/calendar.test.ts`

## Change (TDD: failing tests first)

1. `calendar.ts`: add `chipCompetitions(matches: UpcomingMatch[], selected: Set<string>): string[]` — the competitions present in `matches` plus every selected code, without duplicates, sorted with the same order as `competitionsOf` (`COMPETITION_ORDER`, unknown codes last).
2. `index.astro`: the chip row uses `chipCompetitions(matches, selectedCompetitions)`. A selected code with no match that day renders as a pressed chip with its `shortName(code, code)` label; clicking it untoggles it as any other chip. Everything else (Todas, Ver todas, saving the selection, empty message) stays as it is.
3. Tests in `calendar.test.ts`:
   - `chipCompetitions` with matches of `E0`, `SP1` and selected `{"UCL"}` returns `["E0", "SP1", "UCL"]`.
   - With selected `{"SP1"}` and matches of `E0`, `SP1` returns `["E0", "SP1"]` (no duplicates).
   - With an empty selection it equals `competitionsOf(matches)`.
   - Existing tests pass unchanged.

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
