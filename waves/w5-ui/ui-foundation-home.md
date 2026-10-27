# Task B: ui-foundation-home

Read the whole plan `docs/superpowers/plans/2026-10-27-ui-es-redesign.md` and do **Task B** only. Other workers do the other tasks in parallel; stay inside your allowed files and never commit anything else.

Reference files outside this worktree (read-only, absolute paths):
- Approved visual mockup: `/mnt/data/projects/analisis/.superpowers/brainstorm/67728-1793055210/content/ui-direction.html`
- Design rules (binding for UI edits): `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/craft-floor.md`, `/mnt/data/projects/analisis/.claude/skills/impeccable/reference/operate.md`
- Pre-delivery checklist: `/mnt/data/projects/analisis/.claude/skills/ui-ux-pro-max/references/pro-rules.md`
- Never run anything under `/mnt/data/projects/analisis/.claude/skills/impeccable/scripts/`.

Data contract: `contract/data-contract.md` and `contract/example/`.

## Allowed files

- `site/package.json`
- `site/package-lock.json`
- `site/src/styles/tokens.css`
- `site/src/styles/global.css`
- `site/src/layouts/Base.astro`
- `site/src/components/AppHeader.astro`
- `site/src/components/ThemeToggle.astro`
- `site/src/components/Icon.astro`
- `site/src/lib/theme.ts`
- `site/src/lib/calendar.ts`
- `site/src/lib/types.ts`
- `site/src/pages/index.astro`
- `site/test/calendar.test.ts`
- `site/test/theme.test.ts`

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
