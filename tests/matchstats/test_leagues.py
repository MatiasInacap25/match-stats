from datetime import date

from matchstats.leagues import (
    SECOND_DIVISION,
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


def test_league_catalogue_order_and_second_divisions():
    assert list(TOP_LEAGUES) == ["E0", "SP1", "I1", "D1", "F1"]
    assert TOP_LEAGUES["E0"] == "Premier League"
    assert SECOND_DIVISION == {"E0": "E1", "SP1": "SP2", "I1": "I2", "D1": "D2", "F1": "F2"}
