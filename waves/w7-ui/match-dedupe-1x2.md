# Task: match-dedupe-1x2

On the match page, the "Partido" market tab repeats the 1X2 outcomes (`Gana local`, `Empate`, `Gana visita`) that are already shown as the three cards above it (`renderOutcomes`). Remove them from the market rows only.

Plan context: `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` (Task C).

## Allowed files

- `site/src/lib/render.ts`
- `site/test/render.test.ts`

## Change (TDD)

1. Failing test first: the rendered "Partido" market rows (the function that renders market rows for scope `match`) do not contain `Gana local`, `Empate` or `Gana visita`, but still contain `Ambos marcan` and `Más de 2.5 goles`; `renderOutcomes` still renders the three cards.
2. Make it pass by excluding market ids `1`, `X`, `2` from the market rows. Do not change `markets.ts`, `renderOutcomes`, or anything else.

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
