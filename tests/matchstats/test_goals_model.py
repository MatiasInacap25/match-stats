from datetime import date, timedelta

import numpy as np
import pytest

from matchstats.goals_model import fit_goals_model
from matchstats.match import Match

REF_DATE = date(2026, 10, 26)
# Spread chosen so ~90 matches can separate neighbouring teams: with a narrower spread
# (e.g. +-0.4) the per-team standard error (~0.15-0.2) swamps the true differences.
TRUE_ATTACK = {"Arsenal": 0.8, "Chelsea": 0.5, "Everton": 0.2, "Fulham": -0.2, "Leeds": -0.5, "Wolves": -0.8}
TRUE_DEFENSE = {"Arsenal": -0.3, "Chelsea": -0.2, "Everton": -0.1, "Fulham": 0.1, "Leeds": 0.2, "Wolves": 0.3}
TRUE_HOME_ADVANTAGE = 0.3


def _match(home: str, away: str, hg: int, ag: int, when: date) -> Match:
    return Match(
        div="E0",
        season="2627",
        date=when,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        home_xg=None,
        away_xg=None,
        home_shots=0,
        away_shots=0,
        home_sot=0,
        away_sot=0,
        home_corners=0,
        away_corners=0,
        home_yellow=0,
        away_yellow=0,
        home_red=0,
        away_red=0,
    )


def _synthetic_matches() -> list[Match]:
    """6 teams, 3 double round-robins (90 matches) simulated from known parameters."""
    rng = np.random.default_rng(7)
    teams = list(TRUE_ATTACK)
    pairs = [(h, a) for h in teams for a in teams if h != a]
    matches: list[Match] = []
    for cycle in range(3):
        order = rng.permutation(len(pairs))
        for idx in order:
            home, away = pairs[idx]
            lam = np.exp(TRUE_ATTACK[home] + TRUE_DEFENSE[away] + TRUE_HOME_ADVANTAGE)
            mu = np.exp(TRUE_ATTACK[away] + TRUE_DEFENSE[home])
            hg, ag = int(rng.poisson(lam)), int(rng.poisson(mu))
            days_ago = int(rng.integers(1, 300)) + cycle * 300
            matches.append(_match(home, away, hg, ag, REF_DATE - timedelta(days=days_ago)))
    return matches


@pytest.fixture(scope="module")
def fitted() -> dict:
    return fit_goals_model(_synthetic_matches(), REF_DATE)


def test_recovers_home_advantage(fitted: dict) -> None:
    assert abs(fitted["home_advantage"] - TRUE_HOME_ADVANTAGE) < 0.1


def test_recovers_team_order(fitted: dict) -> None:
    fitted_order = sorted(fitted["teams"], key=lambda t: fitted["teams"][t]["attack"])
    true_order = sorted(TRUE_ATTACK, key=TRUE_ATTACK.get)
    assert fitted_order == true_order


def test_attack_sums_to_zero(fitted: dict) -> None:
    total = sum(team["attack"] for team in fitted["teams"].values())
    assert abs(total) < 1e-6


def test_rho_bounded(fitted: dict) -> None:
    assert -0.2 <= fitted["rho"] <= 0.2


def test_time_decay_weights_recent_matches() -> None:
    matches = _synthetic_matches()
    # Wolves: old matches are big losses, recent matches are big wins.
    old = date(2024, 3, 1)
    recent = date(2026, 10, 1)
    extra = []
    for opponent in ["Arsenal", "Chelsea", "Everton"]:
        extra.append(_match(opponent, "Wolves", 4, 0, old))
        extra.append(_match("Wolves", opponent, 0, 4, old))
        extra.append(_match(opponent, "Wolves", 0, 4, recent))
        extra.append(_match("Wolves", opponent, 4, 0, recent))
    data = matches + extra

    decayed = fit_goals_model(data, REF_DATE, xi=0.01)
    flat = fit_goals_model(data, REF_DATE, xi=0.0)

    assert decayed["teams"]["Wolves"]["attack"] > flat["teams"]["Wolves"]["attack"]


def test_output_shape_matches_contract() -> None:
    matches = _synthetic_matches()
    result = fit_goals_model(matches, REF_DATE)

    assert set(result) == {"home_advantage", "rho", "teams"}
    assert set(result["teams"]) == {m.home for m in matches} | {m.away for m in matches}
    for team in result["teams"].values():
        assert set(team) == {"attack", "defense"}
        assert isinstance(team["attack"], float)
        assert isinstance(team["defense"], float)
        assert team["attack"] == round(team["attack"], 4)
        assert team["defense"] == round(team["defense"], 4)
    assert result["home_advantage"] == round(result["home_advantage"], 4)
    assert result["rho"] == round(result["rho"], 4)


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError):
        fit_goals_model([], REF_DATE)
