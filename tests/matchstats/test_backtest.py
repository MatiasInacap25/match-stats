from datetime import date, timedelta

import numpy as np
import pytest

from matchstats import backtest
from matchstats.backtest import evaluate, predict_1x2
from matchstats.goals_model import fit_goals_model
from matchstats.match import Match

START = date(2025, 7, 1)
TRUE_ATTACK = {"Arsenal": 0.8, "Chelsea": 0.4, "Everton": 0.0, "Fulham": -0.2, "Leeds": -0.5, "Wolves": -0.7}
TRUE_DEFENSE = {"Arsenal": -0.3, "Chelsea": -0.1, "Everton": 0.0, "Fulham": 0.1, "Leeds": 0.2, "Wolves": 0.3}
TRUE_HOME_ADVANTAGE = 0.3


def _match(home: str, away: str, hg: int, ag: int, when: date) -> Match:
    return Match(
        div="E0",
        season="2526",
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


def _synthetic_matches(seed: int, cycles: int = 6) -> list[Match]:
    """6 teams, a double round-robin per cycle, spread evenly over about 2 seasons."""
    rng = np.random.default_rng(seed)
    teams = list(TRUE_ATTACK)
    pairs = [(h, a) for h in teams for a in teams if h != a]
    matches: list[Match] = []
    span_days = 2 * 365
    for cycle in range(cycles):
        for idx in rng.permutation(len(pairs)):
            home, away = pairs[idx]
            lam = np.exp(TRUE_ATTACK[home] + TRUE_DEFENSE[away] + TRUE_HOME_ADVANTAGE)
            mu = np.exp(TRUE_ATTACK[away] + TRUE_DEFENSE[home])
            hg, ag = int(rng.poisson(lam)), int(rng.poisson(mu))
            offset = int(rng.integers(0, span_days // cycles))
            when = START + timedelta(days=cycle * (span_days // cycles) + offset)
            matches.append(_match(home, away, hg, ag, when))
    return matches


@pytest.fixture(scope="module")
def goals() -> dict:
    return {
        "home_advantage": 0.25,
        "rho": -0.05,
        "teams": {
            "Arsenal": {"attack": 0.5, "defense": -0.2},
            "Wolves": {"attack": -0.4, "defense": 0.3},
        },
    }


def test_predict_1x2_sums_to_one(goals: dict) -> None:
    home, draw, away = predict_1x2(goals, "Arsenal", "Wolves")

    assert home + draw + away == pytest.approx(1.0)
    assert min(home, draw, away) > 0
    assert home > away


def test_predict_1x2_rejects_unknown_team(goals: dict) -> None:
    with pytest.raises(ValueError):
        predict_1x2(goals, "Arsenal", "Nowhere FC")


def test_model_beats_baseline_on_synthetic_strengths() -> None:
    matches = _synthetic_matches(seed=5)

    result = evaluate(matches)

    assert result["n"] > 0
    assert result["log_loss"] < result["baseline_log_loss"]
    assert result["brier"] < result["baseline_brier"]


def test_no_lookahead(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[date, list[Match]]] = []
    real_fit = fit_goals_model

    def spy(matches: list[Match], ref_date: date, **kwargs) -> dict:
        calls.append((ref_date, list(matches)))
        return real_fit(matches, ref_date, **kwargs)

    monkeypatch.setattr(backtest, "fit_goals_model", spy)

    evaluate(_synthetic_matches(seed=5))

    assert calls
    for ref_date, fit_inputs in calls:
        assert all(m.date < ref_date for m in fit_inputs)


def test_unknown_teams_are_skipped() -> None:
    matches = _synthetic_matches(seed=5)
    debut = START + timedelta(days=400)
    matches.append(_match("Newcomers", "Wolves", 1, 0, debut))
    matches.append(_match("Wolves", "Newcomers", 0, 2, debut + timedelta(days=1)))

    result = evaluate(matches)

    assert result["skipped"] >= 2
    assert result["n"] + result["skipped"] <= len(matches)
