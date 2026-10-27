from collections import defaultdict
from dataclasses import dataclass

from matchstats.match import Match

STAT_FIELDS: dict[str, tuple[str, str]] = {
    "corners": ("home_corners", "away_corners"),
    "cards": ("home_cards", "away_cards"),
    "shots": ("home_shots", "away_shots"),
    "shots_on_target": ("home_sot", "away_sot"),
}

PREVIOUS_SEASON_WEIGHT = 0.5
DIGITS = 4


@dataclass
class _Side:
    """Weighted sums per team. `home_*` covers the team's home matches, `away_*` its away matches."""

    home_w: float = 0.0
    home_for: float = 0.0
    home_against: float = 0.0
    away_w: float = 0.0
    away_for: float = 0.0
    away_against: float = 0.0


def fit_stat_model(matches: list[Match], stat: str, current_season: str, shrink: float = 5.0) -> dict:
    """Fit one stat (see STAT_FIELDS) and return the contract `stats.<name>` object."""
    if stat not in STAT_FIELDS:
        raise ValueError(f"Unknown stat: {stat}")
    if not matches:
        raise ValueError(f"No matches to fit {stat}")

    home_field, away_field = STAT_FIELDS[stat]
    weights = [_weight(match, current_season) for match in matches]
    home_counts = [getattr(match, home_field) for match in matches]
    away_counts = [getattr(match, away_field) for match in matches]

    avg_home = _weighted_mean(home_counts, weights)
    avg_away = _weighted_mean(away_counts, weights)

    sides: dict[str, _Side] = defaultdict(_Side)
    for match, weight, home_count, away_count in zip(matches, weights, home_counts, away_counts):
        home = sides[match.home]
        home.home_w += weight
        home.home_for += weight * home_count
        home.home_against += weight * away_count

        away = sides[match.away]
        away.away_w += weight
        away.away_for += weight * away_count
        away.away_against += weight * home_count

    ratios: dict[str, dict[str, float]] = {}
    for team, side in sides.items():
        ratios[team] = {
            "home_for": _shrunk(side.home_for, side.home_w, avg_home, shrink),
            "home_against": _shrunk(side.home_against, side.home_w, avg_away, shrink),
            "away_for": _shrunk(side.away_for, side.away_w, avg_away, shrink),
            "away_against": _shrunk(side.away_against, side.away_w, avg_home, shrink),
        }

    team_obs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    total_obs: list[tuple[float, float]] = []
    for match in matches:
        home_mu = avg_home * ratios[match.home]["home_for"] * ratios[match.away]["away_against"]
        away_mu = avg_away * ratios[match.away]["away_for"] * ratios[match.home]["home_against"]
        home_count = getattr(match, home_field)
        away_count = getattr(match, away_field)

        team_obs[match.home].append((home_count, home_mu))
        team_obs[match.away].append((away_count, away_mu))
        total_obs.append((home_count + away_count, home_mu + away_mu))

    all_team_obs = [obs for rows in team_obs.values() for obs in rows]

    return {
        "avg_home": round(avg_home, DIGITS),
        "avg_away": round(avg_away, DIGITS),
        "dispersion_team": _dispersion(all_team_obs),
        "dispersion_total": _dispersion(total_obs),
        "teams": {
            team: {name: round(value, DIGITS) for name, value in team_ratios.items()}
            for team, team_ratios in sorted(ratios.items())
        },
    }


def _weight(match: Match, current_season: str) -> float:
    return 1.0 if match.season == current_season else PREVIOUS_SEASON_WEIGHT


def _weighted_mean(values: list[int], weights: list[float]) -> float:
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _shrunk(weighted_sum: float, weight: float, average: float, shrink: float) -> float:
    """Shrink the raw ratio (weighted mean / league average) toward 1. No matches on that side means 1."""
    if weight == 0:
        return 1.0
    raw = 1.0 if average == 0 else (weighted_sum / weight) / average
    return (weight * raw + shrink * 1.0) / (weight + shrink)


def _dispersion(observations: list[tuple[float, float]]) -> float | None:
    """Method of moments for negative binomial size; None when the data is not overdispersed."""
    numerator = sum(mu * mu for _, mu in observations)
    denominator = sum((x - mu) ** 2 - mu for x, mu in observations)
    if denominator <= 0:
        return None
    return round(numerator / denominator, DIGITS)
