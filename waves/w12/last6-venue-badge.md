# Task: last6-venue-badge

User request (2026-10-30, verbatim): "al historial de partidos agregale un circulo que adentro tenga una letra de L (local) o V (visitante) para saber si ese partido el equipo jugaba de local o de visitante" — confirmed: in the **Últimos 6** lists of each team only (not in Historial / head to head).

Design rules: `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` (Global constraints, tokens) and `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`.

## Allowed files

- `site/src/lib/render.ts`
- `site/src/styles/match.css`
- `site/test/render.test.ts`

## Change (TDD)

- In `renderLastMatches`, each row gets a **circle** (fully round, ~22 px, 1.5 px border in `--muted`, transparent fill, letter in `--text`, weight 700, tabular) containing `L` when the team played at home (`venue === "H"`) or `V` when away (`venue === "A"`), placed right before the opponent name. It must look clearly different from the square result chip (`G`/`E`/`P`), which stays as is.
- The circle replaces the words `vs` / `en` before the opponent (the circle now carries that meaning).
- Accessibility: the circle has `aria-label="Local"` or `aria-label="Visitante"` and `title` with the same text; the letter itself is `aria-hidden="true"`.
- Works in dark and light themes (tokens only, no raw hex) and at 360 px.
- Failing tests first: a home match row contains the `L` circle with `aria-label="Local"`; an away row the `V` circle with `aria-label="Visitante"`; rows no longer contain `vs ` / `en ` before the opponent; the result chip is still rendered; `renderHeadToHead` output is unchanged (no venue circle).

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
