# Task C: ui-match-page

Read the whole plan `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` and do **Task C** only. Task A and Task B are already merged into your base: use `site/src/layouts/Base.astro` (props `{ title }`, named slot `header-start`), `site/src/components/Icon.astro`, and the `global.css` classes `.page`, `.card`, `.seg`, `.seg-btn`, `.num`, `.muted`, `.accent` exactly as they exist now (read them first). Look at `site/src/pages/index.astro` to match its conventions (data loading, error states, theming).

Reference files outside this worktree (read-only, absolute paths):
- Approved visual mockup: `/mnt/data/projects/analisis/.superpowers/brainstorm/67728-1793055210/content/ui-direction.html`
- Design rules (binding for UI edits): `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`, `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/operate.md`
- Pre-delivery checklist: `/mnt/data/projects/analisis/.claude/skills/ui-ux-pro-max/references/pro-rules.md`
- Never run anything under `/mnt/data/projects/analisis/.claude/skills/impeccable/scripts/`.

Data contract: `contract/data-contract.md` and `contract/example/`.

## Allowed files

- `site/src/pages/match.astro`
- `site/src/styles/match.css`
- `site/src/lib/render.ts`
- `site/src/lib/markets.ts`
- `site/test/render.test.ts`
- `site/test/markets.test.ts`

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
