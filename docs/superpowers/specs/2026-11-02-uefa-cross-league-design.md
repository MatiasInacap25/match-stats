# UEFA cross-league analysis and new leagues — design

Date: 2026-11-02. Status: draft for user approval.

## Intent

The user follows the Champions League, Europa League and Conference League in the home calendar (added in wave w13) and wants the same **market probabilities** the site shows for league matches (1X2, goals, BTTS, corners, shots, cards) for UEFA matches. Today every UEFA match is listed without analysis, because the models are fitted per league and the two teams almost always play in different leagues.

User requests, verbatim:

- 2026-11-02: "ya aparecen, pero quiero agregarles analisis estadisticos"
- 2026-11-02: "quiero ver las probabilidades de mercado, tambien agrega las ligas de los demas equipos de champions"
- 2026-11-02 (approach): "si, la opción 1"
- 2026-11-02: "ligas completas en el sitio, par los demas equipos (como los de noruega o austria trae los datos que puedas, como historial de partidos, goles, estadisticas de la temporada, )"

## Goals

1. **Four new full leagues**: Eredivisie (`N1`), Jupiler Pro League (`B1`), Süper Lig (`T1`) and Super League Greece (`G1`), with the same treatment as the current 7: league files, head to head, calendar matches, filter chip, comparator, match pages with all markets.
2. **Goals-only leagues for UEFA teams**: Eliteserien (Norway, `NOR`) and Austrian Bundesliga (`AUT`). Their teams get whatever data the source has: goals model, season stats from results (played, W/D/L, position, points, goals for/against, BTTS %, over 2.5 %, clean sheets), last 6 matches (score and result only), head to head. No shots, corners, cards or xG exist for them.
3. **Cross-league market probabilities** for UEFA matches (UCL, UEL, UECL) where both teams are in any league we have data for, using league strength calibrated from past UEFA results (approach 1 below).
4. A UEFA match page that shows both teams' data side by side, each from its own league.

## Non-goals

- No data or analysis for teams whose league has no free source: Shakhtar (Ukraine), Slavia Praha (Czechia), Slovan Bratislava (Slovakia), Sabah (Azerbaijan), and any other UEFA team outside the leagues above. Their matches stay listed without analysis.
- No change to how league matches of the existing 7 leagues are modelled or shown.
- NOR and AUT are **not** full leagues in the site: no calendar entries for their league matches, no chip, not in the comparator. They exist as data for UEFA matches only. (My call: the user asked for full leagues for the Champions leagues with full stats, and "the data you can" for Norway and Austria.)
- Europa / Conference teams from other leagues (Scotland, Denmark, Poland, Switzerland…) are out of scope for now; the same mechanism can add them later.

## Anti-goals

- Probabilities that look precise but ignore league level: a Galatasaray dominating the Süper Lig must not look stronger than Aston Villa just because its domestic numbers are bigger.
- Invented league factors that cannot be checked against data.
- Breaking the nightly build because of a new source (rules below).

## Failure rules (my call)

- The original 7 leagues stay hard requirements, exactly as today (`validate_output` fails the build without them).
- The new leagues (N1, B1, T1, G1, NOR, AUT) are soft: when a source is unreachable the downloader's cached CSV is used if present; if there is no usable data, or the league fails its own validation, that league is dropped with a warning and the build continues. `index.leagues` then omits it, the site shows no chip for it, and UEFA pairs that need its file show data-less listing (no probabilities).
- The validator checks the 7 required leagues first, in order, followed by any present optional leagues in registry order.

## Delivery order (my call)

Everything except cross-league probabilities ships even if the backtest gate fails: the 4 new full leagues, NOR/AUT data, and the UEFA match page with side-by-side team data. The cross-league goals model is the last wave and only switches probabilities on.

## Data sources (verified 2026-11-02)

| Code | League | Results + stats | Upcoming fixtures |
|---|---|---|---|
| N1 | Eredivisie | football-data `mmz4281/<season>/N1.csv`, full columns incl. `HxG`, `HS`, `HST`, `HC`, `HY` | fixturedownload `eredivisie-2026` |
| B1 | Jupiler Pro League | `mmz4281/<season>/B1.csv`, full columns | no fixturedownload slug found; fall back to football-data `fixtures.csv` (existing fallback path) — builder may look for a slug |
| T1 | Süper Lig | `mmz4281/<season>/T1.csv`, full columns | fixturedownload `super-lig-2026` |
| G1 | Super League Greece | `mmz4281/<season>/G1.csv`, full columns; **14 teams** | as B1 |
| NOR | Eliteserien | `https://www.football-data.co.uk/new/NOR.csv`: one file for all seasons, columns `Country,League,Season,Date,Time,Home,Away,HG,AG,Res,…odds`; `Season` is a calendar year (`2026`) | not needed |
| AUT | Austrian Bundesliga | `new/AUT.csv`, same shape; `Season` is `2026/2027` | not needed |
| — | Past UEFA results | fixturedownload `champions-league-YYYY`, `europa-league-YYYY`, `conference-league-YYYY` (scores, 189/189/153 matches per season for 2025) | — |

Notes: football-data URLs answer with a 302 redirect, so downloads must follow redirects (the existing downloader already works for `mmz4281`). `new/CZE.csv` and `new/UKR.csv` do not exist.

## Approaches considered

1. **Calibrate league strength from past UEFA results (chosen by the user).** Fit one strength offset per league from past UEFA matches, then shift each team's domestic attack/defense by its league's offset before running the existing Dixon-Coles math. Real data, checkable by backtest. Costs a new model and a backtest.
2. Fixed factors per league typed in by hand (e.g. UEFA country coefficients). Fast, but the numbers are unverifiable. Rejected.
3. No adjustment: use each team's domestic numbers as they are. Cheap, but misleading in exactly the lopsided matches. Rejected.

## How it works

### League registry

The hard-coded "7 leagues" assumption (`TOP_LEAGUES`, `COUNTRY_DIVISIONS`, `MIN_TEAMS = 16`, `validate_output` requiring exactly the 7 codes, the site's `COMPETITION_ORDER` and short names, the contract text) becomes a registry of leagues with, per league: code, name, short name, country divisions for head to head, source kind (`full` from `mmz4281`, `goals_only` from `new/<CC>.csv`), season format, minimum team count, and whether it is shown in the site (full league) or data-only. `G1` needs a minimum of 14 teams; NOR and AUT their own minimums (16 and 12).

Order everywhere: E0, SP1, I1, D1, F1, E1, P1, N1, B1, T1, G1, then UCL, UEL, UECL, DFB. NOR and AUT are not in the site order.

### Goals-only leagues

A parser for the `new/` CSV shape maps rows to the existing `Match` with stat fields absent. Their league file has `goals` and `teams` (season stats with stat fields `null`, `last6` with stat fields `null`) and no `stats` block (or an empty one — builder's call, documented in the contract). Their season code maps from the calendar year for NOR (`2026`) and from `2026/2027` for AUT to whatever the build uses for "current season".

### League strength (cross-league goals model)

- Each league `L` gets an offset `s_L` (log-goals scale), with one league fixed as reference (`E0`, `s = 0`).
- For a UEFA match between H (league `LH`) and A (league `LA`), the goals model uses
  `lambda_home = exp(attack[H] + s[LH] + defense[A] - s[LA] + home_advantage_uefa)` and
  `lambda_away = exp(attack[A] + s[LA] + defense[H] - s[LH])`,
  where `attack`/`defense` are the teams' domestic parameters (which already carry their league's scoring level), `home_advantage_uefa` is fitted on UEFA matches, and `rho` is the average of the two leagues' `rho` (builder may fit it instead).
- **Fitting**: for each past UEFA season (at least 2025 and 2024, builder may use more), fit each involved league's domestic goals model as of that season, map both UEFA teams to their domestic parameters, and fit the offsets and `home_advantage_uefa` by maximum likelihood on the UEFA scores, with an L2 penalty pulling offsets toward 0 (leagues with few UEFA matches stay near neutral). Teams that cannot be mapped to a league we have are dropped from fitting.
- **Parameterisation is the builder's choice by backtest** (my call). `fit_goals_model` re-centres attack to mean 0, so a league's scoring level sits in `defense` and in its domestic `home_advantage`; a single offset per league mixes "high-scoring" with "strong". The builder may use separate attack/defense offsets, re-centre on league mean goals, or keep the formula above, and picks the version that wins the held-out backtest. The formula above is the starting point, not a lock.
- **Backtest gate**: hold out the most recent complete UEFA season. The calibrated model must beat (a) the unadjusted model (`s = 0`) and (b) the base-rate baseline on log loss for 1X2. Report both in the backtest output. If it does not beat the unadjusted model, stop and report to the user before shipping cross-league probabilities.
- **When the fit runs** (my call): in the nightly build. Past-season domestic fits do not change, so the builder may cache them. If the past-UEFA feeds are down or the fit fails, the build keeps the previous `uefa.json` (copied from the current output directory); if there is none, UEFA matches show data without probabilities. The nightly build records the held-out metrics in `uefa.json`, and when the calibrated model does not beat the unadjusted one it writes `"calibrated": false` and the site hides cross-league probabilities.
- **Same-league UEFA pairs** (e.g. two E0 sides in the UCL) (my call): use the existing domestic model and page, as today (`league` is set). The offsets would cancel; the only difference is UEFA vs domestic home advantage, which is not worth a second code path. These matches are excluded from the offset fit's held-out metric only if the builder finds they distort it.

### Cross-league stat markets (corners, shots, shots on target, cards)

There is no free source of UEFA corners/shots/cards to calibrate against (fixturedownload has scores only). So:

- Expected count for each side uses the existing formula with the league average taken as the geometric mean of the two leagues' averages, and each team's own multipliers.
- **My call, flagged for the user**: earlier in the conversation I said these would get "a softer adjustment". A league-strength adjustment for these stats cannot be calibrated, so the design ships them **unadjusted** and the match page shows a short note under those markets: they come from each team's domestic numbers and are not adjusted for league level. Scaling shots by the fitted goal offsets is a possible later improvement once there is data to check it.
- If either team is from a goals-only league, the stat markets are hidden and only goal markets show.

### Output contract changes

- `index.json` → `leagues`: the 11 full leagues in order (NOR, AUT are not listed here).
- New `uefa.json` (name is the builder's call): the fitted offsets per league (including NOR, AUT), `home_advantage_uefa`, the seasons used, and the backtest metrics.
- `leagues/NOR.json`, `leagues/AUT.json` (goals-only shape) and their `h2h` files.
- `upcoming` UEFA items: `league` stays the rule for same-league pairs; add `home_league` and `away_league` (the league code of each team, or `null` when unknown). The site shows analysis when both are non-null.
- Team names: UEFA feed names resolve against **every** league we have, not just the 7. New aliases go in `team_names.py` (the test suite checks each target exists).

### Site

- Calendar: chips for the 4 new full leagues; UEFA matches with both leagues known get probabilities and an analysis link.
- Match page: accepts a UEFA match (e.g. `?competition=UCL&home=…&home_league=SP1&away=…&away_league=E0`, exact params are the builder's call), loads both league files plus `uefa.json`, shows markets from the cross-league model, the season comparison and last 6 of each team from its own league (with the league named next to each team), head to head only when both teams share a country (otherwise hidden), and the note on stat markets.
- Comparator: the 4 new leagues appear in its league selector (same-league comparisons only, as today).

## Constraints

- Free, keyless sources only; the nightly GitHub Action must stay within its current runtime (builder measures the new build time and reports it).
- Same project stack and conventions: Python build in `src/matchstats`, Astro site with client-side probability math, contract in `contract/`, tests in `tests/` and `site/test/`, workers via `orchestra` waves.
- All UI copy in Spanish, as the rest of the site.

## Left to the builder

- Exact file and function names, the registry's shape, and the URL parameters of the UEFA match page.
- Season-code mapping for NOR/AUT.
- How many past UEFA seasons to fit on and the L2 strength (choose by the held-out backtest).
- fixturedownload slugs for B1/G1 if they exist; otherwise the `fixtures.csv` fallback.
- Aliases needed for the new leagues' fixture names.
