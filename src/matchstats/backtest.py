"""Walk-forward backtest of the goals model against a historical-frequency baseline.

Run: uv run python -m matchstats.backtest --league E0 --season 2526 --cache data/raw
"""

import argparse
import bisect
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import poisson

from matchstats.goals_model import _tau, fit_goals_model
from matchstats.ingest import load_matches
from matchstats.leagues import TOP_LEAGUES, recent_seasons, season_code
from matchstats.match import Match

MAX_GOALS = 10
HISTORY_SEASONS = 4  # the evaluated season plus three earlier seasons used for training


def predict_1x2(goals: dict, home: str, away: str) -> tuple[float, float, float]:
    """P(home win), P(draw), P(away win) from the Dixon-Coles score matrix.

    The matrix is truncated at MAX_GOALS per side and renormalized, as in site/src/lib/probability.ts.
    """
    matrix = _score_matrix(goals, home, away)
    return (
        float(np.tril(matrix, -1).sum()),
        float(np.trace(matrix)),
        float(np.triu(matrix, 1).sum()),
    )


def evaluate(
    matches: list[Match],
    refit_every_days: int = 14,
    warmup_days: int = 60,
    eval_from: date | None = None,
) -> dict:
    """Walk-forward evaluation of the goals model.

    The first refit happens warmup_days after the first match (or on eval_from, if later).
    Each refit fits on every match dated before the refit date and predicts the matches
    dated within the following refit_every_days. Matches with a team unknown to the fit
    are skipped. Metrics cover the predicted matches only; the baseline is the home/draw/away
    frequency of all matches dated before each prediction (uniform when there is none).
    """
    if refit_every_days <= 0:
        raise ValueError("refit_every_days must be positive")

    ordered = sorted(matches, key=lambda m: m.date)
    if not ordered:
        return _metrics([], [], [], [], skipped=0)

    dates = [m.date for m in ordered]
    history = _outcome_history(ordered, dates)

    first_eval = ordered[0].date + timedelta(days=warmup_days)
    if eval_from is not None:
        first_eval = max(first_eval, eval_from)

    model_losses: list[float] = []
    model_briers: list[float] = []
    base_losses: list[float] = []
    base_briers: list[float] = []
    skipped = 0

    refit = first_eval
    last = ordered[-1].date
    while refit <= last:
        window_end = refit + timedelta(days=refit_every_days)
        start = bisect.bisect_left(dates, refit)
        end = bisect.bisect_left(dates, window_end)
        train = ordered[:start]
        if train and end > start:
            goals = fit_goals_model(train, refit)
            for idx in range(start, end):
                match = ordered[idx]
                if match.home not in goals["teams"] or match.away not in goals["teams"]:
                    skipped += 1
                    continue
                outcome = _outcome(match)
                probs = predict_1x2(goals, match.home, match.away)
                base = _baseline(history, bisect.bisect_left(dates, match.date))
                model_losses.append(_log_loss(probs, outcome))
                model_briers.append(_brier(probs, outcome))
                base_losses.append(_log_loss(base, outcome))
                base_briers.append(_brier(base, outcome))
        refit = window_end

    return _metrics(model_losses, model_briers, base_losses, base_briers, skipped)


def _lambdas(goals: dict, home: str, away: str) -> tuple[float, float]:
    teams = goals["teams"]
    for team in (home, away):
        if team not in teams:
            raise ValueError(f"Unknown team: {team}")
    lam = math.exp(teams[home]["attack"] + teams[away]["defense"] + goals["home_advantage"])
    mu = math.exp(teams[away]["attack"] + teams[home]["defense"])
    return lam, mu


def _score_matrix(goals: dict, home: str, away: str) -> np.ndarray:
    lam, mu = _lambdas(goals, home, away)
    k = np.arange(MAX_GOALS + 1)
    home_goals, away_goals = np.meshgrid(k, k, indexing="ij")
    independent = np.outer(poisson.pmf(k, lam), poisson.pmf(k, mu))
    matrix = independent * _tau(home_goals, away_goals, lam, mu, goals["rho"])
    return matrix / matrix.sum()


def _outcome(match: Match) -> int:
    """0 = home win, 1 = draw, 2 = away win."""
    if match.home_goals > match.away_goals:
        return 0
    if match.home_goals == match.away_goals:
        return 1
    return 2


def _outcome_history(ordered: list[Match], dates: list[date]) -> np.ndarray:
    """cumulative[i] = outcome counts of the first i matches (sorted by date)."""
    one_hot = np.zeros((len(ordered), 3))
    one_hot[np.arange(len(ordered)), [_outcome(m) for m in ordered]] = 1
    return np.vstack([np.zeros(3), np.cumsum(one_hot, axis=0)])


def _baseline(history: np.ndarray, count_before: int) -> tuple[float, float, float]:
    """Frequencies of the matches dated before the prediction; uniform when there are none."""
    counts = history[count_before]
    total = counts.sum()
    if total == 0:
        return (1 / 3, 1 / 3, 1 / 3)
    freq = counts / total
    return (float(freq[0]), float(freq[1]), float(freq[2]))


def _log_loss(probs: tuple[float, float, float], outcome: int) -> float:
    return -math.log(probs[outcome])


def _brier(probs: tuple[float, float, float], outcome: int) -> float:
    return sum((p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs))


def _metrics(
    model_losses: list[float],
    model_briers: list[float],
    base_losses: list[float],
    base_briers: list[float],
    skipped: int,
) -> dict:
    n = len(model_losses)
    if n == 0:
        return {
            "n": 0,
            "skipped": skipped,
            "log_loss": None,
            "brier": None,
            "baseline_log_loss": None,
            "baseline_brier": None,
        }
    return {
        "n": n,
        "skipped": skipped,
        "log_loss": sum(model_losses) / n,
        "brier": sum(model_briers) / n,
        "baseline_log_loss": sum(base_losses) / n,
        "baseline_brier": sum(base_briers) / n,
    }


def _season_start(code: str) -> date:
    """'2526' -> 2025-07-01."""
    return date(2000 + int(code[:2]), 7, 1)


def _format(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest of the goals model.")
    parser.add_argument("--league", required=True, choices=sorted(TOP_LEAGUES))
    parser.add_argument("--season", required=True, help="season code to evaluate, e.g. 2526")
    parser.add_argument("--cache", type=Path, default=Path("data/raw"), help="CSV cache directory")
    args = parser.parse_args(argv)

    seasons = recent_seasons(args.season, HISTORY_SEASONS)
    matches = load_matches([args.league], seasons, args.cache, season_code(date.today()))
    result = evaluate(matches, eval_from=_season_start(args.season))

    print(f"league: {args.league}")
    print(f"season: {args.season}")
    print(f"n: {result['n']}")
    print(f"skipped: {result['skipped']}")
    print(f"log_loss: {_format(result['log_loss'])}")
    print(f"baseline_log_loss: {_format(result['baseline_log_loss'])}")
    print(f"brier: {_format(result['brier'])}")
    print(f"baseline_brier: {_format(result['baseline_brier'])}")


if __name__ == "__main__":
    main()
