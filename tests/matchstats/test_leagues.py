from datetime import date

from matchstats.leagues import (
    COUNTRY_DIVISIONS,
    DATA_LEAGUES,
    LEAGUES,
    SITE_LEAGUES,
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


def test_registry_order_and_flags():
    assert [spec.code for spec in LEAGUES] == [
        "E0", "SP1", "I1", "D1", "F1", "E1", "P1", "N1", "B1", "T1", "G1", "NOR", "AUT",
    ]
    assert [spec.required for spec in LEAGUES] == [True] * 7 + [False] * 6
    assert [spec.code for spec in LEAGUES if not spec.in_site] == ["NOR", "AUT"]


def test_registry_minimum_teams_and_sources():
    by_code = {spec.code: spec for spec in LEAGUES}
    assert by_code["G1"].min_teams == 14
    assert by_code["AUT"].min_teams == 12
    assert by_code["NOR"].min_teams == 16
    assert by_code["N1"].min_teams == 16
    assert [spec.code for spec in LEAGUES if spec.source == "goals_only"] == ["NOR", "AUT"]
    assert by_code["NOR"].new_csv == "NOR"
    assert by_code["AUT"].new_csv == "AUT"
    assert by_code["N1"].new_csv is None


def test_registry_fixture_slugs():
    by_code = {spec.code: spec for spec in LEAGUES}
    assert by_code["N1"].fixture_slug == "eredivisie"
    assert by_code["T1"].fixture_slug == "super-lig"
    assert by_code["B1"].fixture_slug is None
    assert by_code["G1"].fixture_slug is None
    assert by_code["E0"].fixture_slug == "epl"


def test_registry_views():
    assert list(SITE_LEAGUES) == ["E0", "SP1", "I1", "D1", "F1", "E1", "P1", "N1", "B1", "T1", "G1"]
    assert SITE_LEAGUES["N1"] == "Eredivisie"
    assert list(DATA_LEAGUES) == [spec.code for spec in LEAGUES]
    assert DATA_LEAGUES["AUT"] == "Austrian Bundesliga"
    assert list(TOP_LEAGUES) == ["E0", "SP1", "I1", "D1", "F1", "E1", "P1"]
