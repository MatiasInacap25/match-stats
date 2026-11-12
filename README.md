# analisis (matchstats)

A free, static site for the top five European leagues (Premier League, La Liga,
Serie A, Bundesliga, Ligue 1). Pick two teams from the same league and see
market probabilities (match and per-team), season stats, each team's last six
matches, and head to head.

- **Python** (`src/matchstats`): downloads football-data.co.uk CSVs, fits a
  Dixon-Coles goals model and negative-binomial stat rates per league, and
  writes JSON files to `site/public/data/` (format in `contract/data-contract.md`).
- **Site** (`site/`): Astro. It reads those JSON files and computes every
  probability in the browser. No odds, no bookmaker data, no accounts.
- **Data updates**: run the build locally and push `site/public/data`; Vercel
  redeploys on that commit. (The GitHub Actions nightly job was removed.)

## Local use

```bash
# Build the data (downloads CSVs into data/raw, cached between runs)
uv run matchstats build --out site/public/data --cache data/raw

# Run the site
cd site && npm run dev

# Run the site on the example data in contract/example (no download)
cd site && npm run dev:example

# Backtest the goals model on one season (log loss and Brier vs baseline)
uv run python -m matchstats.backtest --league E0 --season 2526 --cache data/raw

# Tests
uv run pytest -q
cd site && npm test
```

A failed build (for example, one CSV download returns garbage) fails validation
and leaves the previously published files untouched.

## Goals model backtest (season 2025/26, walk-forward, 1X2)

Run on 2026-10-27. Baseline = home/draw/away frequencies seen before each match. Lower is better.

| League | Matches | Log loss | Baseline log loss | Brier | Baseline Brier |
|--------|--------:|---------:|------------------:|------:|---------------:|
| E0 Premier League | 378 | 1.0241 | 1.0855 | 0.6146 | 0.6571 |
| SP1 La Liga | 376 | 0.9910 | 1.0493 | 0.5882 | 0.6320 |
| I1 Serie A | 379 | 0.9953 | 1.0887 | 0.5939 | 0.6603 |
| D1 Bundesliga | 305 | 0.9782 | 1.0705 | 0.5781 | 0.6477 |
| F1 Ligue 1 | 304 | 1.0020 | 1.0667 | 0.6000 | 0.6446 |

The model beats the baseline in every league. That says its probabilities are sane, not that they beat bookmaker odds.

## Agent workflow

Parallel Claude Code workers are launched with `orchestra`. See
[waves/README.md](waves/README.md).

## Setup you do once (user steps)

1. Create a GitHub repository under your account and push this code to it.
2. In Vercel, import the repository and set **Root Directory** to `site`.
   Vercel reads `site/vercel.json` for the build settings.

## Known limitation

How football-data.co.uk records a second yellow (in `HY`, `HR` or both) is not
verified. Cards are counted as `HY + 2 × HR` (yellow = 1, red = 2).
