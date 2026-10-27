# Spanish UI, Redesign and Today/Tomorrow Calendar Plan

> Executed through `orchestrate-waves`. Each worker reads this whole file plus `contract/data-contract.md`.

**Goal:** The site is fully in Spanish, follows the approved "programa de partido bajo los focos" direction in dark (default) and light themes, and its home page has a Hoy / Mañana calendar of the 5 leagues' matches.

**Approved by the user (2026-10-27):** Spanish UI; dark and light themes; main use is at night on a phone; calendar shows **only today and tomorrow**. Visual direction approved from the mockup `.superpowers/brainstorm/67728-1793055210/content/ui-direction.html` (read it: it is the visual reference).

**Design skills:** `.claude/skills/impeccable/reference/craft-floor.md` and `.claude/skills/impeccable/reference/operate.md` are binding for every UI edit (read them before editing UI). Do **not** run any script from `.claude/skills/impeccable/scripts/` (it downloads a binary). `.claude/skills/ui-ux-pro-max/references/pro-rules.md` holds the pre-delivery checklist.

## Global constraints

- **Copy:** neutral, professional Spanish (tú forms: "Elige", not "Elegí"). Decimal point for lines and numbers, as Betano shows them ("Más de 2.5 goles", "Esperados: 4.36"). Team names exactly as in the data. HTML `lang="es"`.
- **Dates and times:** formatted in the viewer's local time zone with `Intl.DateTimeFormat("es", …)`: dates like `lun 27 oct`, times `21:00` (24 h).
- **Mode:** Operate (product UI). Mobile-first, readable at 360 px, no horizontal page scroll. Touch targets ≥ 44 px. Visible focus rings. `prefers-reduced-motion` respected. Transitions 150–250 ms.
- **Icons:** inline SVG (Lucide shapes), 1.75 px stroke, never emoji or Unicode glyphs.
- **Fonts:** Barlow (400/500/600/700) and Barlow Semi Condensed (500/600/700), self-hosted through `@fontsource/barlow` and `@fontsource/barlow-semi-condensed` (no Google Fonts request). `font-variant-numeric: tabular-nums` on all numbers.
- **Theme:** default follows `prefers-color-scheme`; a header toggle switches dark/light and stores the choice in `localStorage` key `ms-theme` (`"dark" | "light"`), applied as `data-theme` on `<html>` by an inline script in `<head>` before first paint (no flash).
- **Tokens** (CSS custom properties on `:root[data-theme="dark"]` and `:root[data-theme="light"]`; components use only these, never raw hex):

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#0e1311` | `#f5f3ee` |
| `--surface` | `#151b18` | `#fffdf8` |
| `--surface-2` | `#1c2420` | `#efece4` |
| `--line` | `#26302b` | `#dcd7cb` |
| `--text` | `#e9ece8` | `#18201c` |
| `--muted` | `#9aa69f` | `#5b655f` |
| `--accent` | `#f2b84b` | `#8a5a00` |
| `--accent-ink` | `#1a1305` | `#fff8e8` |
| `--win` | `#7fd19b` | `#1d7a45` |
| `--loss` | `#f08a7e` | `#b3362b` |
| `--draw` | `#c9cfca` | `#5b655f` |
| `--bar` | `#2b3530` | `#e4dfd3` |
| `--focus` | `#f2b84b` | `#8a5a00` |

  Also theme text selection (`::selection` with `--accent`/`--accent-ink`), the caret and scrollbars from these tokens. Radius 10 px for controls/cards; 1 px `--line` borders; no gradients, no glass, no colored side borders, no eyebrow/kicker labels above headings.
- **Accent rule:** the accent marks only (a) the favorite in 1X2 and (b) markets with probability ≥ 60 %. Everything else is neutral.

## Spanish copy glossary (exact strings)

Home: title `Match Stats`; labels `Liga`, `Local`, `Visitante`; select placeholder `Elige un equipo`; button `Analizar`; calendar tabs `Hoy` and `Mañana` (each with its date, e.g. `Hoy · lun 27 oct`); updated line `Actualizado a las HH:MM`; empty day `Todavía no hay partidos publicados para este día.`; theme toggle aria-labels `Cambiar a tema claro` / `Cambiar a tema oscuro`.

Match page: back link `Inicio`; subtitle `<Liga> · Temporada 2026/27`; 1X2 cards `Gana local`, `Empate`, `Gana visita`; market tabs `Partido`, `<home>`, `<away>`; markets `Ambos marcan`, `Más de 2.5 goles`, `Más de 9.5 córners`, `Más de 4.5 tarjetas`, `Más de 24.5 tiros`, `Más de 8.5 tiros al arco`; per team `Más de 1.5 goles`, `Más de 4.5 córners`, `Más de 1.5 tarjetas`, `Más de 12.5 tiros`, `Más de 4.5 tiros al arco`; expected line `Esperados: 4.36` (`Esperadas:` for tarjetas). Sections `Temporada`, `Últimos 6 · <team>`, `Historial`. Season toggle `Todo`, `Local`, `Visitante`. Season rows: `Partidos`, `Posición`, `Puntos`, `Ganados`, `Empatados`, `Perdidos`, `Goles a favor`, `Goles en contra`, `xG a favor`, `xG en contra`, `Tiros a favor`, `Tiros en contra`, `Tiros al arco a favor`, `Tiros al arco en contra`, `Córners a favor`, `Córners en contra`, `Amarillas por partido`, `Rojas por partido`, `Ambos marcan`, `Más de 2.5 goles`, `Vallas invictas`. Result chips `G` / `E` / `P`; venue words `vs` (home) / `en` (away). Last-6 detail line: `xG 1.2–1.9 · Tiros 18–10 · Al arco 6–5 · Córners 6–6 · Tarjetas 3–3`; footnote `Tarjetas en puntos: amarilla 1, roja 2.` Head to head summary: `Últimos 6: <home> 5 victorias · 0 empates · <away> 1 victoria · 5.00 goles por partido · ambos marcan 6/6`; empty `Sin enfrentamientos previos.` Errors: `Equipo no encontrado.`, `Elige una liga y dos equipos en el inicio.`, link `Volver al inicio`; data load failure `No se pudieron cargar los datos. Intenta de nuevo más tarde.`

## Data contract change (Task A owns the contract files)

`index.json` gains `upcoming`: the 5 leagues' fixtures from football-data's `fixtures.csv` dated from today − 1 to today + 2 (Europe/Madrid dates, inclusive; changed during integration so viewers west of Madrid still get their today), sorted by kickoff:

```json
"upcoming": [{"league": "E0", "kickoff_utc": "2026-10-27T20:00:00Z", "home": "Arsenal", "away": "Brighton"}]
```

`fixtures.csv` times are UK local time (Europe/London); convert with `zoneinfo` to UTC. `today` stays as it is (compatibility). The site groups `upcoming` into Hoy / Mañana by the **viewer's local date** of `kickoff_utc`; that is why the build ships three days.

---

## Wave 5 (parallel)

### Task A: `data-upcoming` (Python + contract)

**Files:** `src/matchstats/build.py`, `tests/matchstats/test_build.py`, `contract/data-contract.md`, `contract/example/index.json`.

- [ ] Failing tests: `test_upcoming_covers_three_days_sorted` (fixtures on today−1, today, today+1, today+2, today+3 → only the middle three, sorted by `kickoff_utc`, only top-5 leagues); `test_kickoff_converted_from_uk_time` (`26/10/2026 20:00` → `2026-10-26T20:00:00Z` (GMT); `24/10/2026 20:00` → `2026-10-24T19:00:00Z` (BST)); existing tests still pass; `validate_output` requires `upcoming` to be a list.
- [ ] Implement; update the contract doc section for `index.json` and add a 2-item `upcoming` to `contract/example/index.json` (Arsenal–Brighton today, Chelsea–Arsenal tomorrow, relative to the example's `generated_at` date 2026-10-26).
- [ ] `uv run pytest -q` → PASS. Commit `feat(matchstats): publish upcoming fixtures with UTC kickoff`.

### Task B: `ui-foundation-home` (site)

**Files:** `site/package.json`, `site/package-lock.json`, `site/src/styles/tokens.css`, `site/src/styles/global.css`, `site/src/layouts/Base.astro`, `site/src/components/AppHeader.astro`, `site/src/components/ThemeToggle.astro`, `site/src/components/Icon.astro`, `site/src/lib/theme.ts`, `site/src/lib/calendar.ts`, `site/src/lib/types.ts`, `site/src/pages/index.astro`, `site/test/calendar.test.ts`, `site/test/theme.test.ts`.

**Produces (Task C relies on these exactly):**
- `Base.astro` — props `{ title: string }`; renders `<html lang="es">`, the no-flash theme script, imports `tokens.css` and `global.css` and the fonts, `<AppHeader>` and a `<main class="page">` slot. Optional named slot `header-start` for a back link.
- `Icon.astro` — props `{ name: "sun" | "moon" | "chevron-left" | "calendar"; size?: number }`.
- `global.css` utility classes Task C may use: `.page` (max-width 640 px, 16 px side padding), `.card`, `.seg` + `.seg-btn` + `.seg-btn[aria-selected="true"]` (segmented control), `.num` (tabular numbers), `.muted`, `.accent`.
- `types.ts` — add `UpcomingMatch { league: string; kickoff_utc: string; home: string; away: string }` and `upcoming?: UpcomingMatch[]` on `IndexData`.
- `calendar.ts` — `groupByLocalDay(matches: UpcomingMatch[], now: Date, timeZone?: string): { today: UpcomingMatch[]; tomorrow: UpcomingMatch[] }` and `formatDayLabel(date: Date, timeZone?: string): string` (`lun 27 oct`), `formatKickoff(iso: string, timeZone?: string): string` (`21:00`).
- `theme.ts` — `resolveTheme(stored: string | null, prefersDark: boolean): "dark" | "light"`.

Home page (`index.astro`, uses `Base`): league segmented chips (5 leagues, short names: `Premier`, `LaLiga`, `Serie A`, `Bundesliga`, `Ligue 1`), `Local`/`Visitante` selects limited to that league, `Analizar` (disabled when equal or empty). Calendar below: `Hoy` / `Mañana` segmented tabs with dates; each match row: kickoff (local time), league short name, `Local vs Visita`, and `1` / `Más de 2.5` probabilities computed with the existing `markets.ts`/`probability.ts` (load each league's JSON once, lazily); row links to `/match?league=…&home=…&away=…`. A match whose team is missing from the league data shows without probabilities, still linked. Empty day → the glossary sentence. Data load failure → the glossary error.

- [ ] Failing tests: `groupByLocalDay` splits by the given time zone (e.g. a `2026-10-27T23:30:00Z` kickoff is "tomorrow" in `Europe/Madrid` on Oct 27 but "today" in `America/Santiago`); excludes other days; sorted by kickoff. `formatDayLabel` → `lun 27 oct`; `formatKickoff` → 24 h. `resolveTheme` (stored wins; otherwise system).
- [ ] Implement; `npm install @fontsource/barlow @fontsource/barlow-semi-condensed`.
- [ ] `cd site && npm test && npm run build` → PASS. Commit `feat(site): spanish themed foundation and home calendar`.

## Wave 6

### Task C: `ui-match-page` (site)

**Files:** `site/src/pages/match.astro`, `site/src/styles/match.css`, `site/src/lib/render.ts`, `site/src/lib/markets.ts`, `site/test/render.test.ts`, `site/test/markets.test.ts`.

**Consumes:** `Base.astro`, `Icon.astro`, `global.css` classes from Task B.

Match page per the mockup: back link `Inicio` (header-start slot), title `<home> vs <away>`, subtitle with league name and season, 1X2 as three cards (favorite in accent), market tabs `Partido` / `<home>` / `<away>` (segmented, keyboard accessible with arrow keys, `role="tablist"`), each market row: name, percentage, expected line, 4 px probability bar (accent when ≥ 60 %). Then `Temporada` as a two-column comparison (home value · label · away value, the better value in bold; "better" = higher for for-stats and points, lower for against-stats and position; xG and null values render `—`) with the `Todo / Local / Visitante` toggle; `Últimos 6 · <team>` as compact two-line rows (chip G/E/P, date, `vs`/`en` opponent, score; detail line); `Historial` with summary and compact rows (date, home score away, detail line Tiros/Al arco/Córners/Tarjetas). All copy from the glossary; markets labels move to Spanish in `markets.ts`.

- [ ] Update tests to the Spanish strings first (watch them fail), plus: `test favorite gets accent class`, `test market ≥ 60% gets accent class`, `test season comparison bolds the better side (position lower is better)`.
- [ ] Implement. `cd site && npm test && npm run build` → PASS. Commit `feat(site): spanish redesigned match page`.

## Integration (orchestrator)

Real data build, both themes at 360 px and desktop in the browser, keyboard pass on tabs and toggle, contrast spot check, then show the user before merging to `main`.
