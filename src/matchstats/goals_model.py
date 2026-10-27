"""Dixon-Coles goals model, fitted per league. Contract: contract/data-contract.md (goals)."""

from datetime import date

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from matchstats.match import Match

RHO_BOUNDS = (-0.2, 0.2)
_DECIMALS = 4
_SCALE = 10**_DECIMALS


def fit_goals_model(matches: list[Match], ref_date: date, xi: float = 0.002, l2: float = 0.1) -> dict:
    """Fit attack/defense per team, home advantage and the low-score correction rho.

    Matches are weighted by exp(-xi * days_before_ref_date); matches dated on or after
    ref_date get weight 1. Returns the contract's `goals` object with floats rounded to 4 decimals.
    """
    if not matches:
        raise ValueError("cannot fit the goals model without matches")

    teams = sorted({m.home for m in matches} | {m.away for m in matches})
    index = {team: i for i, team in enumerate(teams)}
    n = len(teams)

    home_idx = np.array([index[m.home] for m in matches])
    away_idx = np.array([index[m.away] for m in matches])
    home_goals = np.array([m.home_goals for m in matches])
    away_goals = np.array([m.away_goals for m in matches])
    days_before = np.array([max((ref_date - m.date).days, 0) for m in matches], dtype=float)
    weights = np.exp(-xi * days_before)

    def unpack(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        return theta[:n], theta[n : 2 * n], theta[2 * n], theta[2 * n + 1]

    def objective(theta: np.ndarray) -> float:
        attack, defense, home_adv, rho = unpack(theta)
        log_lam = attack[home_idx] + defense[away_idx] + home_adv
        log_mu = attack[away_idx] + defense[home_idx]
        lam, mu = np.exp(log_lam), np.exp(log_mu)
        log_pois = (
            home_goals * log_lam - lam - gammaln(home_goals + 1)
            + away_goals * log_mu - mu - gammaln(away_goals + 1)
        )
        log_likelihood = np.sum(weights * (np.log(_tau(home_goals, away_goals, lam, mu, rho)) + log_pois))
        penalty = l2 * (np.sum(attack**2) + np.sum(defense**2))
        return float(-log_likelihood + penalty)

    bounds = [(None, None)] * (2 * n + 1) + [RHO_BOUNDS]
    result = minimize(objective, np.zeros(2 * n + 2), method="L-BFGS-B", bounds=bounds)
    attack, defense, home_adv, rho = unpack(result.x)

    # Attack and defense trade a constant: moving c from defense to attack keeps every lambda.
    shift = attack.mean()
    attack = attack - shift
    defense = defense + shift

    attack_rounded = _round_zero_sum(attack)
    defense_rounded = np.round(defense, _DECIMALS)
    return {
        "home_advantage": round(float(home_adv), _DECIMALS),
        "rho": round(float(rho), _DECIMALS),
        "teams": {
            team: {"attack": float(attack_rounded[i]), "defense": float(defense_rounded[i])}
            for team, i in index.items()
        },
    }


def _tau(home_goals: np.ndarray, away_goals: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float) -> np.ndarray:
    """Dixon-Coles dependence factor for the four low scores; 1 everywhere else."""
    tau = np.ones_like(lam)
    tau = np.where((home_goals == 0) & (away_goals == 0), 1 - lam * mu * rho, tau)
    tau = np.where((home_goals == 0) & (away_goals == 1), 1 + lam * rho, tau)
    tau = np.where((home_goals == 1) & (away_goals == 0), 1 + mu * rho, tau)
    tau = np.where((home_goals == 1) & (away_goals == 1), 1 - rho, tau)
    return np.maximum(tau, 1e-10)


def _round_zero_sum(values: np.ndarray) -> np.ndarray:
    """Round to 4 decimals so the rounded values still sum to exactly zero.

    Plain rounding can leave the sum off by a few 1e-4; largest-remainder rounding
    keeps the sum of the rounded values equal to the rounded sum of the exact values.
    """
    scaled = values * _SCALE
    floors = np.floor(scaled)
    missing = int(round(scaled.sum())) - int(floors.sum())
    order = np.argsort(-(scaled - floors))
    floors[order[:missing]] += 1
    return floors / _SCALE
