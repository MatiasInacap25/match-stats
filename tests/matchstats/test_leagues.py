from datetime import date

from matchstats.leagues import (
    COUNTRY_DIVISIONS,
    TOP_LEAGUES,
    recent_seasons,
    season_code,
    season_label,
)


def test_season_code_boundaries():
    assert season_code(date(2026, 6, 30)) == "2526"
    assert season_code(date(2026, 7, 1)) == "2627"
    assert season_label("2627") == "2026/27"
    assert recent_seasons("2627", 3) == ["2627", "2526", "2425"]


def test_league_catalogue_order_and_names():
    assert list(TOP_LEAGUES) == ["E0", "SP1", "I1", "D1", "F1", "E1", "P1"]
    assert TOP_LEAGUES == {
        "E0": "Premier League",
        "SP1": "La Liga",
        "I1": "Serie A",
        "D1": "Bundesliga",
        "F1": "Ligue 1",
        "E1": "Championship",
        "P1": "Primeira Liga",
    }


def test_country_divisions_top_first_for_every_league():
    assert COUNTRY_DIVISIONS == {
        "E0": ("E0", "E1", "E2"),
        "SP1": ("SP1", "SP2"),
        "I1": ("I1", "I2"),
        "D1": ("D1", "D2"),
        "F1": ("F1", "F2"),
        "E1": ("E0", "E1", "E2"),
        "P1": ("P1",),
    }
    assert list(COUNTRY_DIVISIONS) == list(TOP_LEAGUES)
