# Task: site-polish (integration fixes found by the orchestrator with real data)

You are fixing three gaps between the match page and the validated design. Stay inside your allowed files.

- Spec: `docs/superpowers/specs/2026-10-26-match-stats-design.md` (Part 1, "The page")
- Validated mockup: section 3 "Last 6 matches" shows per match: result, opponent, home/away, score, xG, shots, shots on target, corners, cards. Section 4 "Head to head" shows per meeting: date, score, shots, shots on target, corners, cards.
- Data contract (binding): `contract/data-contract.md`, examples in `contract/example/`.

## Allowed files

- `site/src/lib/render.ts`
- `site/src/pages/match.astro`
- `site/test/render.test.ts`

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`

## Changes (TDD: write each failing test first, watch it fail, then implement)

1. **Last 6: add a shots-on-target column.** In `renderLastMatches`, add a column headed `SoT` right after `Shots`, showing `shots_on_target_for-shots_on_target_against` (same format as Shots, e.g. `6-3`).
   Test: `renderLastMatches` output for the example's first Arsenal match contains a `SoT` header and the cell `6-3`.
2. **Head to head: add stats per meeting.** In `renderHeadToHead`, after the score columns, add columns `Shots`, `SoT`, `Corners`, `Cards`, each formatted `home-away` from the meeting's `home_shots/away_shots`, `home_shots_on_target/away_shots_on_target`, `home_corners/away_corners`, `home_cards/away_cards`. Keep the existing summary line and "No previous meetings" behavior unchanged.
   Test: for the example pair `Arsenal|Brighton`, the 2026-03-01 row contains `10-15`, `3-6`, `4-6` and `3-1`; the existing summary and empty-state tests still pass.
3. **League name in the match page subtitle.** `match.astro` shows `<league name> · Season <season>` (e.g. `Premier League · Season 2026/27`) instead of the league code. Take the name from `index.json` (`leagues[].name`, loaded with the existing `loadIndex()`); fall back to the code if it is missing.

Do not change markets, probability code, data loading paths or any other file. English UI copy.
