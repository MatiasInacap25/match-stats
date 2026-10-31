# Task: comparator-top

On the home page, the collapsed comparator ("Comparar equipos") currently sits at the very bottom, after the whole calendar (40+ matches on busy days). The plan wording "the calendar is the first content below the header" was wrong; the user's intent is that the comparator is collapsed so the calendar is visible when the page opens.

Plan context: `docs/superpowers/plans/2026-10-30-leagues-filters.md` (Task G).

## Allowed files

- `site/src/pages/index.astro`

## Change

- Move the collapsible comparator (its `Comparar equipos` button and panel) to directly below the page title `Match Stats`, above the calendar. Collapsed it is a single full-width row; expanded it pushes the calendar down. Keep everything else (closed by default, `aria-expanded`/`aria-controls`, animation, reduced motion) as it is.
- Verify there is no other change in behavior: run the tests and the build.

## Test command (must pass before you finish)

`cd site && npm ci && npm test && npm run build`
