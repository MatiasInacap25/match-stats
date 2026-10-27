# Data contract: nightly job → site

The nightly job (Python, `uv run matchstats build --out site/public/data`) writes these files. The site (Astro, client-side TypeScript) reads them and computes every probability in the browser. Both sides test against the examples in `contract/example/`.

All numbers are plain JSON numbers. Missing values are `null`. Dates are ISO `YYYY-MM-DD`. Team names are exactly as football-data.co.uk writes them (single source, so no aliasing).

## `index.json`

```json
{
  "generated_at": "2026-10-26T02:05:00Z",
  "season": "2026/27",
  "leagues": [{"code": "E0", "name": "Premier League", "teams": ["Arsenal", "..."]}],
  "today": [{"league": "E0", "date": "2026-10-26", "time": "20:00", "home": "Arsenal", "away": "Brighton"}],
  "upcoming": [{"league": "E0", "kickoff_utc": "2026-10-26T20:00:00Z", "home": "Arsenal", "away": "Brighton"}]
}
```

- `leagues`: exactly the 5 top leagues, in this order: `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1. `teams` is the sorted list of the current season's teams.
- `today`: matches of these 5 leagues dated today (Europe/Madrid) in football-data's `fixtures.csv`. Empty list when there are none. Kept for compatibility.
- `upcoming`: matches of these 5 leagues whose Europe/Madrid date is from today to today + 2 (inclusive), from football-data's `fixtures.csv`, sorted by kickoff. Empty list when there are none. Each item has:
  - `league`: league code (one of the 5 above).
  - `kickoff_utc`: kickoff as an ISO 8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ`. `fixtures.csv` gives UK local time (Europe/London), so the build converts it with `zoneinfo` (GMT or BST by date).
  - `home`, `away`: team names exactly as in the data.
  The site groups `upcoming` into Hoy / Mañana by the viewer's local date of `kickoff_utc`, which is why the build ships three days.

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
- Meetings come from the top division and the second division (`E1`, `SP2`, `I2`, `D2`, `F2`) of that country, for the 10 most recent seasons, newest first.
