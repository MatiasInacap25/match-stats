# Data contract: nightly job → site

The nightly job (Python, `uv run matchstats build --out site/public/data`) writes these files. The site (Astro, client-side TypeScript) reads them and computes every probability in the browser. Both sides test against the examples in `contract/example/`.

All numbers are plain JSON numbers. Missing values are `null`. Dates are ISO `YYYY-MM-DD`. Team names are football-data.co.uk names (the same names as `leagues[].teams`) wherever a team resolves; `upcoming` keeps the source name for a team that does not (see `upcoming`).

## `index.json`

```json
{
  "generated_at": "2026-10-26T02:05:00Z",
  "season": "2026/27",
  "leagues": [{"code": "E0", "name": "Premier League", "teams": ["Arsenal", "..."]}],
  "today": [{"league": "E0", "date": "2026-10-26", "time": "20:00", "home": "Arsenal", "away": "Brighton"}],
  "upcoming": [{"competition": "E0", "competition_name": "Premier League", "kickoff_utc": "2026-10-26T20:00:00Z", "home": "Arsenal", "away": "Brighton", "league": "E0"}]
}
```

- `leagues`: the 7 required leagues first, in this order: `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1, `E1` Championship, `P1` Primeira Liga. Then the optional leagues that are present in the build, in this order: `N1` Eredivisie, `B1` Jupiler Pro League, `T1` Süper Lig, `G1` Super League Greece. An optional league whose source has no usable data, or that fails its checks, is left out with a warning and the build continues. `teams` is the sorted list of the current season's teams. Each league needs at least `min_teams` teams: 16 for every league except `G1` (14).
- `today`: matches of the 7 required leagues dated today (Europe/Madrid) in football-data's `fixtures.csv`. Empty list when there are none. Kept for compatibility.
- `upcoming`: league matches of the site leagues (the 7 required and the optional ones present in `leagues`), UEFA matches (Champions League, Europa League, Conference League) and DFB-Pokal matches whose Europe/Madrid date is from today − 1 to today + 2 (inclusive). Sorted by kickoff, then competition order (E0, SP1, I1, D1, F1, E1, P1, N1, B1, T1, G1, UCL, UEL, UECL, DFB), then `home`. Empty list when there are none. Each item has:
  - `competition`: league code (one of the 11 site leagues above), `UCL`, `UEL`, `UECL` for the UEFA competitions, or `DFB` for DFB-Pokal.
  - `competition_name`: `Premier League`, `La Liga`, `Serie A`, `Bundesliga`, `Ligue 1`, `Championship`, `Primeira Liga`, `Eredivisie`, `Jupiler Pro League`, `Süper Lig`, `Super League Greece`, `Champions League`, `Europa League`, `Conference League` or `DFB-Pokal`.
  - `kickoff_utc`: kickoff as an ISO 8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ`. fixturedownload gives UTC. OpenLigaDB gives German local time (Europe/Berlin), and `fixtures.csv` gives UK local time (Europe/London); the build converts both with `zoneinfo` (by date).
  - `home`, `away`: the football-data name when the team resolves in the league's current-season teams, otherwise the source name. Aliases are in `src/matchstats/team_names.py`.
  - `league`: the league whose data has both teams. For a league match it is the league itself, or `null` when that league is not in `leagues` (dropped by the build). For a UCL, UEL, UECL or DFB-Pokal match it is the one site league in `leagues` whose current teams include both sides, or `null` when there is no such league (the site shows no probabilities and no analysis link).
  - Sources: league matches come from fixturedownload (`epl`, `la-liga`, `serie-a`, `bundesliga`, `ligue-1`, `championship`, `primeira-liga`, `eredivisie`, `super-lig`; season year 2026). `B1` and `G1` have no fixturedownload feed and come from `fixtures.csv` only. A league whose feed fails falls back to `fixtures.csv` for that league. UEFA matches come from fixturedownload (`champions-league`, `europa-league`, `conference-league`, season year 2026) with no `fixtures.csv` fallback. DFB-Pokal comes from `https://api.openligadb.de/getmatchdata/dfb/2026`. A failed source is skipped with a warning and never fails the build.
  The site groups `upcoming` into Hoy / Mañana by the viewer's local date of `kickoff_utc`, which is why the build ships four days (west of Madrid, the viewer's today can still be Madrid's yesterday).

## `leagues/<code>.json`

```json
{
  "league": "E0",
  "season": "2026/27",
  "goals": {
    "home_advantage": 0.25,
    "rho": -0.05,
    "teams": {"Arsenal": {"attack": 0.35, "defense": -0.30}}
  },
  "stats": {
    "corners": {
      "avg_home": 5.6, "avg_away": 4.6,
      "dispersion_team": 12.0, "dispersion_total": 15.0,
      "teams": {"Arsenal": {"home_for": 1.2, "home_against": 0.8, "away_for": 1.1, "away_against": 0.9}}
    },
    "cards": {"...": "same shape"},
    "shots": {"...": "same shape"},
    "shots_on_target": {"...": "same shape"}
  },
  "teams": {
    "Arsenal": {
      "season": {
        "all":  {"matches": 9, "position": 1, "points": 22, "won": 7, "drawn": 1, "lost": 1,
                 "goals_for": 2.1, "goals_against": 0.7, "xg_for": 1.9, "xg_against": 0.8,
                 "shots_for": 15.2, "shots_against": 8.9, "shots_on_target_for": 5.9, "shots_on_target_against": 2.8,
                 "corners_for": 6.8, "corners_against": 3.2, "yellow_cards": 1.6, "red_cards": 0.1,
                 "btts_pct": 0.44, "over_2_5_pct": 0.56, "clean_sheets": 5},
        "home": {"...": "same shape, home matches only"},
        "away": {"...": "same shape, away matches only"}
      },
      "last6": [
        {"date": "2026-10-25", "league": "E0", "venue": "H", "opponent": "Brighton",
         "goals_for": 2, "goals_against": 1, "result": "W",
         "xg_for": 1.8, "xg_against": 0.9, "shots_for": 17, "shots_against": 9,
         "shots_on_target_for": 6, "shots_on_target_against": 3,
         "corners_for": 7, "corners_against": 3, "cards_for": 2, "cards_against": 4}
      ]
    }
  }
}
```

Meanings (the TypeScript side relies on these exactly):

- **Goals model** (Dixon-Coles). For home team H and away team A:
  `lambda_home = exp(attack[H] + defense[A] + home_advantage)`, `lambda_away = exp(attack[A] + defense[H])`.
  `defense` is higher for teams that concede more. `rho` is the Dixon-Coles low-score correction.
- **Stat models**, for each of `corners`, `cards`, `shots`, `shots_on_target`:
  expected home team count `= avg_home * teams[H].home_for * teams[A].away_against`,
  expected away team count `= avg_away * teams[A].away_for * teams[H].home_against`.
  `avg_home` and `avg_away` are league means of the stat for the home side and the away side. The ratios are team means divided by those averages, shrunk toward 1.
- **Count distribution**: negative binomial with mean `mu` and size `dispersion` (`p = size / (size + mu)`). `dispersion_team` applies to one team's count, `dispersion_total` to the match total, where the total's mean is the sum of both teams' means. `null` dispersion means Poisson.
- **Cards** are card points: yellow = 1, red = 2 (Betano settlement). `cards_for`/`cards_against` in `last6` use the same points. `season.*.yellow_cards`/`red_cards` are raw per-match counts.
- **Shots** include shots on target (football-data `HS` already does).
- `season.*` values are per-match averages, except `matches`, `position`, `points`, `won`, `drawn`, `lost`, `clean_sheets` (counts) and `*_pct` (0–1 fractions). `position` and `points` are the same in `all`, `home` and `away` (league table). `xg_*` are `null` when football-data has no xG for those matches. When a side has `matches: 0` (e.g. no away games yet), every per-match average and `*_pct` is `null`; counts are `0`; `position` and `points` keep their table values.
- `last6`: the team's 6 most recent matches in its own league's data, newest first. `venue` is `H` or `A`. `result` is `W`, `D` or `L`.

## `h2h/<code>.json`

```json
{
  "league": "E0",
  "pairs": {
    "Arsenal|Brighton": [
      {"date": "2026-03-01", "league": "E0", "home": "Brighton", "away": "Arsenal",
       "home_goals": 1, "away_goals": 2, "home_shots": 10, "away_shots": 15,
       "home_shots_on_target": 3, "away_shots_on_target": 6,
       "home_corners": 4, "away_corners": 6, "home_cards": 3, "away_cards": 1}
    ]
  }
}
```

- Key: the two team names sorted alphabetically, joined by `|`.
- Every pair of current-season teams in that league, including pairs with no meetings (empty list).
- Meetings come from every division of the league's country, for the 10 most recent seasons, newest first: `E0`, `E1`, `E2` for England (`E0` and `E1` leagues); `SP1`, `SP2` for Spain; `I1`, `I2` for Italy; `D1`, `D2` for Germany; `F1`, `F2` for France; `P1` for Portugal. The list is the `divisions` of each league in `LEAGUES` in `src/matchstats/leagues.py`. `N1`, `B1`, `T1` and `G1` have only their own division.
