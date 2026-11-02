"""Cross-league strength of UEFA clubs, fitted on past UEFA results. Contract: contract/data-contract.md (uefa.json).

Each league keeps its own domestic goals model. A league offset (attack and defense) shifts every club of that
league when it plays a club of another league. E0 is the reference and stays at zero.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import poisson

from matchstats.fixture_sources import uefa_fixture_urls
from matchstats.goals_model import _tau, fit_goals_model
from matchstats.leagues import DATA_LEAGUES
from matchstats.match import Match
from matchstats.team_names import resolve

REFERENCE = "E0"
UEFA_SEASONS = 3  # completed UEFA seasons with results, the last one held out by the backtest
DOMESTIC_SEASONS = 3  # domestic seasons before each UEFA season start that fit a league's goals model
L2 = 5.0  # penalty on the squared offsets, against the Poisson log-likelihood summed over matches
MAX_GOALS = 10
_DECIMALS = 4


@dataclass(frozen=True)
class UefaResult:
    year: int  # UEFA season start year: 2025 is 2025/26
    kickoff_utc: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    home_league: str | None
    away_league: str | None


@dataclass(frozen=True)
class _Row:
    """A UEFA match between two different leagues, with both clubs' domestic parameters for its season."""

    year: int
    home_league: str
    away_league: str
    home_goals: int
    away_goals: int
    rho: float
    home_attack: float
    home_defense: float
    away_attack: float
    away_defense: float


def completed_years(current: str, n: int) -> list[int]:
    """The n UEFA seasons before the current one, oldest first: '2627' with n=3 -> [2023, 2024, 2025]."""
    start = 2000 + int(current[:2])
    return [start - n + i for i in range(n)]


def uefa_result_urls(years: list[int]) -> dict[str, str]:
    """Finished-match feeds of the three UEFA competitions, keyed f"{code}-{year}" (e.g. "UCL-2025")."""
    urls = {}
    for year in years:
        season = f"{year % 100:02d}{(year + 1) % 100:02d}"
        for code, url in uefa_fixture_urls(season).items():
            urls[f"{code}-{year}"] = url
    return urls


def parse_uefa_results(text: str, year: int, team_league: Callable[[str], str | None]) -> list[UefaResult]:
    """Finished matches of a fixturedownload feed. `team_league` gives the league code of a feed team name, or None."""
    results = []
    for row in json.loads(text):
        if row.get("HomeTeamScore") is None or row.get("AwayTeamScore") is None:
            continue  # not played yet
        home, away = row["HomeTeam"], row["AwayTeam"]
        results.append(
            UefaResult(
                year=year,
                kickoff_utc=datetime.strptime(row["DateUtc"], "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=UTC),
                home=home,
                away=away,
                home_goals=int(row["HomeTeamScore"]),
                away_goals=int(row["AwayTeamScore"]),
                home_league=team_league(home),
                away_league=team_league(away),
            )
        )
    return results


def domestic_fits(league_matches: dict[str, list[Match]], years: list[int]) -> dict[tuple[str, int], dict]:
    """The goals object of each league for each UEFA season start, fitted on the matches of the seasons before it.

    Only matches dated before 1 July of the season year count, so a season's own results never leak into it.
    A league with no matches in that window has no entry.
    """
    fits = {}
    for code, matches in league_matches.items():
        for year in years:
            cutoff = date(year, 7, 1)
            window = [m for m in matches if date(year - DOMESTIC_SEASONS, 7, 1) <= m.date < cutoff]
            if window:
                fits[(code, year)] = fit_goals_model(window, ref_date=cutoff)
    return fits


def fit_league_offsets(matches: list[UefaResult], domestic: dict[tuple[str, int], dict], l2: float = L2) -> dict:
    """Home advantage and the attack/defense offset of every league, fitted by maximum likelihood."""
    rows = _usable(matches, domestic)
    codes = _league_codes(domestic)
    home_advantage, attack, defense = _fit(rows, codes, l2, with_offsets=True)
    return {
        "home_advantage": _round(home_advantage),
        "offsets": {
            code: {"attack": _round(attack[i]), "defense": _round(defense[i])} for i, code in enumerate(codes)
        },
    }


def backtest(matches: list[UefaResult], domestic: dict[tuple[str, int], dict], l2: float = L2) -> dict:
    """Fits on every UEFA season before the last one and scores the 1X2 outcomes of the last one.

    `log_loss` is the offsets model, `log_loss_unadjusted` the same model with no offsets, and `log_loss_baseline`
    the outcome frequencies of the training seasons.
    """
    rows = _usable(matches, domestic)
    held_out = max(row.year for row in rows)
    train = [row for row in rows if row.year < held_out]
    test = [row for row in rows if row.year == held_out]
    codes = _league_codes(domestic)
    index = {code: i for i, code in enumerate(codes)}

    fitted = _fit(train, codes, l2, with_offsets=True)
    plain = _fit(train, codes, l2, with_offsets=False)
    frequencies = _outcome_frequencies(train)

    model_losses, plain_losses, base_losses = [], [], []
    for row in test:
        outcome = _outcome(row)
        model_losses.append(_loss(_probabilities(row, *fitted, index), outcome))
        plain_losses.append(_loss(_probabilities(row, *plain, index), outcome))
        base_losses.append(-np.log(frequencies[outcome]))

    return {
        "held_out": held_out,
        "matches": len(test),
        "log_loss": _round(np.mean(model_losses)),
        "log_loss_unadjusted": _round(np.mean(plain_losses)),
        "log_loss_baseline": _round(np.mean(base_losses)),
    }


def uefa_document(matches: list[UefaResult], domestic: dict[tuple[str, int], dict], l2: float = L2) -> dict | None:
    """The contract's `uefa.json` object, or None when fewer than two seasons have usable matches."""
    seasons = sorted({row.year for row in _usable(matches, domestic)})
    if len(seasons) < 2:
        return None
    result = backtest(matches, domestic, l2)
    fitted = fit_league_offsets(matches, domestic, l2)
    return {
        "calibrated": result["log_loss"] < result["log_loss_unadjusted"],
        "home_advantage": fitted["home_advantage"],
        "offsets": fitted["offsets"],
        "seasons": seasons,
        "backtest": result,
    }


def _usable(matches: list[UefaResult], domestic: dict[tuple[str, int], dict]) -> list[_Row]:
    """Matches between two different leagues whose clubs both resolve to a team of that season's domestic fit.

    Same-league matches are left out: the domestic model already covers them.
    """
    rows = []
    for match in matches:
        if match.home_league is None or match.away_league is None or match.home_league == match.away_league:
            continue
        home_fit = domestic.get((match.home_league, match.year))
        away_fit = domestic.get((match.away_league, match.year))
        if home_fit is None or away_fit is None:
            continue
        home = resolve(match.home, set(home_fit["teams"]))
        away = resolve(match.away, set(away_fit["teams"]))
        if home is None or away is None:
            continue
        home_params = home_fit["teams"][home]
        away_params = away_fit["teams"][away]
        rows.append(
            _Row(
                year=match.year,
                home_league=match.home_league,
                away_league=match.away_league,
                home_goals=match.home_goals,
                away_goals=match.away_goals,
                rho=(home_fit["rho"] + away_fit["rho"]) / 2,
                home_attack=home_params["attack"],
                home_defense=home_params["defense"],
                away_attack=away_params["attack"],
                away_defense=away_params["defense"],
            )
        )
    return rows


def _league_codes(domestic: dict[tuple[str, int], dict]) -> list[str]:
    """Every league with a domestic fit, in registry order: the reference first."""
    present = {code for code, _ in domestic}
    codes = [code for code in DATA_LEAGUES if code in present]
    if not codes or codes[0] != REFERENCE:
        raise ValueError(f"reference league {REFERENCE} has no domestic fit")
    return codes


def _fit(rows: list[_Row], codes: list[str], l2: float, with_offsets: bool) -> tuple[float, np.ndarray, np.ndarray]:
    """(home_advantage, attack offsets, defense offsets) by maximum likelihood.

    The reference league is index 0 and fixed at zero. With `with_offsets` False only the home advantage is fitted.
    """
    index = {code: i for i, code in enumerate(codes)}
    home_idx = np.array([index[r.home_league] for r in rows], dtype=int)
    away_idx = np.array([index[r.away_league] for r in rows], dtype=int)
    home_goals = np.array([r.home_goals for r in rows], dtype=float)
    away_goals = np.array([r.away_goals for r in rows], dtype=float)
    rho = np.array([r.rho for r in rows], dtype=float)
    home_attack = np.array([r.home_attack for r in rows], dtype=float)
    home_defense = np.array([r.home_defense for r in rows], dtype=float)
    away_attack = np.array([r.away_attack for r in rows], dtype=float)
    away_defense = np.array([r.away_defense for r in rows], dtype=float)
    free = len(codes) - 1

    def unpack(theta: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        if not with_offsets:
            zeros = np.zeros(len(codes))
            return theta[0], zeros, zeros
        attack = np.concatenate(([0.0], theta[1 : 1 + free]))
        defense = np.concatenate(([0.0], theta[1 + free : 1 + 2 * free]))
        return theta[0], attack, defense

    def objective(theta: np.ndarray) -> float:
        advantage, attack, defense = unpack(theta)
        log_lam = home_attack + attack[home_idx] + away_defense + defense[away_idx] + advantage
        log_mu = away_attack + attack[away_idx] + home_defense + defense[home_idx]
        lam, mu = np.exp(log_lam), np.exp(log_mu)
        log_pois = (
            home_goals * log_lam - lam - gammaln(home_goals + 1)
            + away_goals * log_mu - mu - gammaln(away_goals + 1)
        )
        log_likelihood = np.sum(np.log(_tau(home_goals, away_goals, lam, mu, rho)) + log_pois)
        penalty = l2 * (np.sum(attack**2) + np.sum(defense**2))
        return float(-log_likelihood + penalty)

    size = 1 + 2 * free if with_offsets else 1
    result = minimize(objective, np.zeros(size), method="L-BFGS-B")
    return unpack(result.x)


def _probabilities(
    row: _Row, home_advantage: float, attack: np.ndarray, defense: np.ndarray, index: dict[str, int]
) -> tuple[float, float, float]:
    """P(home win), P(draw), P(away win) of one match from the Dixon-Coles score matrix, as backtest.py does."""
    home, away = index[row.home_league], index[row.away_league]
    lam = np.exp(row.home_attack + attack[home] + row.away_defense + defense[away] + home_advantage)
    mu = np.exp(row.away_attack + attack[away] + row.home_defense + defense[home])
    goals = np.arange(MAX_GOALS + 1)
    home_goals, away_goals = np.meshgrid(goals, goals, indexing="ij")
    matrix = np.outer(poisson.pmf(goals, lam), poisson.pmf(goals, mu))
    matrix = matrix * _tau(home_goals, away_goals, lam, mu, row.rho)
    matrix = matrix / matrix.sum()
    return (float(np.tril(matrix, -1).sum()), float(np.trace(matrix)), float(np.triu(matrix, 1).sum()))


def _outcome(row: _Row) -> int:
    """0 = home win, 1 = draw, 2 = away win."""
    if row.home_goals > row.away_goals:
        return 0
    if row.home_goals == row.away_goals:
        return 1
    return 2


def _outcome_frequencies(rows: list[_Row]) -> np.ndarray:
    """Share of home wins, draws and away wins among the rows; uniform when there are none."""
    if not rows:
        return np.full(3, 1 / 3)
    counts = np.bincount([_outcome(r) for r in rows], minlength=3)
    return counts / counts.sum()


def _loss(probs: tuple[float, float, float], outcome: int) -> float:
    return -float(np.log(probs[outcome]))


def _round(value: float) -> float:
    return round(float(value), _DECIMALS) + 0.0  # + 0.0 turns -0.0 into 0.0
