# Task: h2h-year

On the match page, head-to-head rows show dates without the year (e.g. `dom 26 abr`). The history spans 10 seasons, so the same month repeats and dates are ambiguous. Show the year in head-to-head rows only, as `26 abr 2026` (day, short month, year; no weekday), formatted with `Intl.DateTimeFormat("es", …)` in the viewer's time zone like the rest of the page. Last-6 rows keep their current format.

Plan context: `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` (Task C).

## Allowed files

- `site/src/lib/render.ts`
- `site/test/render.test.ts`

## Change (TDD)

1. Failing test first: `renderHeadToHead` for the example pair `Arsenal|Brighton` contains `1 mar 2026` and `14 sept 2025` (check what `Intl` actually outputs for September in `es` and assert that exact string); `renderLastMatches` output is unchanged (existing tests stay green).
2. Implement. Do not change anything else.

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
