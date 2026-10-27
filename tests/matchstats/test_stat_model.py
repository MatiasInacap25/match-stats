import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from matchstats.match import Match
from matchstats.stat_model import STAT_FIELDS, fit_stat_model

CONTRACT_EXAMPLE = Path(__file__).parents[2] / "contract" / "example" / "leagues" / "E0.json"
CURRENT = "2627"
PREVIOUS = "2526"


def make_match(
    home: str,
    away: str,
    season: str = CURRENT,
    home_corners: int = 0,
    away_corners: int = 0,
    home_shots: int = 0,
    away_shots: int = 0,
    home_sot: int = 0,
    away_sot: int = 0,
    home_yellow: int = 0,
    away_yellow: int = 0,
    home_red: int = 0,
    away_red: int = 0,
) -> Match:
    return Match(
        div="E0",
        season=season,
        date=date(2026, 8, 21),
        home=home,
        away=away,
        home_goals=0,
        away_goals=0,
        home_xg=None,
        away_xg=None,
        home_shots=home_shots,
        away_shots=away_shots,
        home_sot=home_sot,
        away_sot=away_sot,
        home_corners=home_corners,
        away_corners=away_corners,
        home_yellow=home_yellow,
        away_yellow=away_yellow,
        home_red=home_red,
        away_red=away_red,
    )


def simulated_matches(draw, rng: np.random.Generator, n: int = 600) -> list[Match]:
    teams = [f"T{i}" for i in range(10)]
    matches = []
    for _ in range(n):
        home, away = rng.choice(len(teams), size=2, replace=False)
        matches.append(
            make_match(
                teams[int(home)],
                teams[int(away)],
                home_corners=int(draw(rng)),
                away_corners=int(draw(rng)),
            )
        )
    return matches


def test_stat_fields_map_to_match_attributes():
    assert STAT_FIELDS == {
        "corners": ("home_corners", "away_corners"),
        "cards": ("home_cards", "away_cards"),
        "shots": ("home_shots", "away_shots"),
        "shots_on_target": ("home_sot", "away_sot"),
    }


def test_league_averages():
    matches = [
        make_match("A", "B", home_corners=6, away_corners=4),
        make_match("B", "C", home_corners=2, away_corners=8),
        make_match("C", "A", home_corners=5, away_corners=3),
    ]

    fitted = fit_stat_model(matches, "corners", CURRENT)

    assert fitted["avg_home"] == pytest.approx(13 / 3, abs=1e-4)
    assert fitted["avg_away"] == pytest.approx(5.0)


def test_previous_season_half_weight():
    matches = [
        make_match("A", "B", season=CURRENT, home_corners=6, away_corners=4),
        make_match("A", "B", season=PREVIOUS, home_corners=2, away_corners=4),
    ]

    fitted = fit_stat_model(matches, "corners", CURRENT)

    # (6 * 1.0 + 2 * 0.5) / (1.0 + 0.5)
    assert fitted["avg_home"] == pytest.approx(7 / 1.5, abs=1e-4)


def test_ratio_shrinks_toward_one():
    matches = [
        make_match("A", "B", home_corners=8, away_corners=4),
        make_match("A", "B", home_corners=8, away_corners=4),
        make_match("B", "A", home_corners=0, away_corners=4),
        make_match("B", "A", home_corners=0, away_corners=4),
    ]

    fitted = fit_stat_model(matches, "corners", CURRENT)

    # A's home mean is 8 against an average of 4: raw 2, shrunk with w=2 and k=5.
    home_for = fitted["teams"]["A"]["home_for"]
    assert 1 < home_for < 2
    assert home_for == pytest.approx(9 / 7, abs=1e-4)


def test_cards_use_points():
    matches = [
        make_match("A", "B", home_yellow=1, home_red=1, away_yellow=1, away_red=1),
    ]

    fitted = fit_stat_model(matches, "cards", CURRENT)

    assert fitted["avg_home"] == 3.0
    assert fitted["avg_away"] == 3.0


def test_overdispersed_data_gives_finite_size():
    rng = np.random.default_rng(11)
    mean, size = 5, 3
    p = size / (size + mean)
    matches = simulated_matches(lambda r: r.negative_binomial(size, p), rng)

    fitted = fit_stat_model(matches, "corners", CURRENT)

    assert fitted["dispersion_team"] is not None
    assert 1.5 < fitted["dispersion_team"] < 6


def test_poisson_data_gives_no_overdispersion():
    rng = np.random.default_rng(11)
    matches = simulated_matches(lambda r: r.poisson(5), rng)

    fitted = fit_stat_model(matches, "corners", CURRENT)

    assert fitted["dispersion_team"] is None or fitted["dispersion_team"] > 30


def test_team_without_away_matches_is_neutral():
    matches = [
        make_match("A", "B", home_corners=6, away_corners=2),
        make_match("B", "C", home_corners=3, away_corners=4),
        make_match("C", "B", home_corners=5, away_corners=1),
    ]

    fitted = fit_stat_model(matches, "corners", CURRENT)

    assert fitted["teams"]["A"]["away_for"] == 1.0
    assert fitted["teams"]["A"]["away_against"] == 1.0


def test_output_shape_matches_contract():
    example = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))
    matches = [
        make_match("Arsenal", "Brighton", home_corners=6, away_corners=3),
        make_match("Brighton", "Chelsea", home_corners=4, away_corners=5),
        make_match("Chelsea", "Arsenal", home_corners=5, away_corners=6),
        make_match("Brighton", "Arsenal", home_corners=3, away_corners=7),
        make_match("Arsenal", "Chelsea", home_corners=7, away_corners=2),
        make_match("Chelsea", "Brighton", home_corners=4, away_corners=4),
    ]

    fitted = fit_stat_model(matches, "corners", CURRENT)

    assert set(fitted) == set(example["stats"]["corners"])
    assert set(fitted["teams"]) == {"Arsenal", "Brighton", "Chelsea"}
    for ratios in fitted["teams"].values():
        assert set(ratios) == {"home_for", "home_against", "away_for", "away_against"}
