from datetime import date

import pytest

from matchstats.match import Match
from matchstats.team_stats import (
    head_to_head,
    last_matches,
    league_table,
    pair_key,
    season_stats,
)


def match(
    home: str,
    away: str,
    hg: int,
    ag: int,
    on: date = date(2026, 8, 1),
    *,
    div: str = "E0",
    hxg: float | None = None,
    axg: float | None = None,
    hs: int = 10,
    aws: int = 10,
    hst: int = 4,
    ast: int = 4,
    hc: int = 5,
    ac: int = 5,
    hy: int = 0,
    ay: int = 0,
    hr: int = 0,
    ar: int = 0,
) -> Match:
    return Match(
        div=div,
        season="2627",
        date=on,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        home_xg=hxg,
        away_xg=axg,
        home_shots=hs,
        away_shots=aws,
        home_sot=hst,
        away_sot=ast,
        home_corners=hc,
        away_corners=ac,
        home_yellow=hy,
        away_yellow=ay,
        home_red=hr,
        away_red=ar,
    )


def test_table_points_and_tiebreak():
    matches = [
        match("A", "B", 2, 0),  # A +2 GD
        match("C", "D", 1, 0),
        match("A", "C", 1, 1),
        match("B", "D", 0, 0),
    ]

    table = league_table(matches)

    # A: 4 pts, GD +2. C: 4 pts, GD +1. D: 1 pt, GD -1. B: 1 pt, GD -2.
    assert table == {"A": (1, 4), "C": (2, 4), "D": (3, 1), "B": (4, 1)}


def test_table_tiebreak_goals_for_then_name():
    matches = [
        match("Zed", "Yak", 2, 2),  # 1 pt, GD 0, GF 2
        match("Alpha", "Beta", 1, 1),  # 1 pt, GD 0, GF 1
        match("Gamma", "Delta", 1, 1),  # 1 pt, GD 0, GF 1
    ]

    table = league_table(matches)

    assert table["Yak"] == (1, 1)
    assert table["Zed"] == (2, 1)
    assert table["Alpha"] == (3, 1)
    assert table["Beta"] == (4, 1)
    assert table["Delta"] == (5, 1)
    assert table["Gamma"] == (6, 1)


def test_season_stats_values():
    matches = [
        # A home: W 2-1, xG 1.5/0.5, cards: yellow 2
        match("A", "B", 2, 1, date(2026, 8, 1), hxg=1.5, axg=0.5, hs=14, aws=8,
              hst=5, ast=2, hc=6, ac=3, hy=2, ay=1),
        # A away: W 3-0, xG 2.1/0.4, red 1 for A
        match("C", "A", 0, 3, date(2026, 8, 8), hxg=0.4, axg=2.1, hs=6, aws=16,
              hst=2, ast=7, hc=2, ac=8, hy=1, ay=0, hr=0, ar=1),
        # A home: D 0-0, no xG, yellow 1
        match("A", "D", 0, 0, date(2026, 8, 15), hs=9, aws=9, hst=3, ast=3,
              hc=4, ac=4, hy=1, ay=3),
    ]
    table = {"A": (1, 7)}

    side = season_stats(matches, "A", table)["all"]

    assert side == {
        "matches": 3,
        "position": 1,
        "points": 7,
        "won": 2,
        "drawn": 1,
        "lost": 0,
        "goals_for": 1.67,
        "goals_against": 0.33,
        "xg_for": 1.8,
        "xg_against": 0.45,
        "shots_for": 13.0,
        "shots_against": 7.67,
        "shots_on_target_for": 5.0,
        "shots_on_target_against": 2.33,
        "corners_for": 6.0,
        "corners_against": 3.0,
        "yellow_cards": 1.0,
        "red_cards": 0.33,
        "btts_pct": 0.333,
        "over_2_5_pct": 0.667,
        "clean_sheets": 2,
    }


def test_home_away_split():
    matches = [
        match("A", "B", 2, 1, date(2026, 8, 1)),
        match("C", "A", 0, 3, date(2026, 8, 8)),
        match("A", "D", 0, 0, date(2026, 8, 15)),
    ]
    table = {"A": (1, 7)}

    stats = season_stats(matches, "A", table)

    assert stats["home"]["matches"] == 2
    assert stats["home"]["won"] == 1
    assert stats["home"]["drawn"] == 1
    assert stats["home"]["goals_for"] == 1.0
    assert stats["home"]["goals_against"] == 0.5
    assert stats["away"]["matches"] == 1
    assert stats["away"]["won"] == 1
    assert stats["away"]["goals_for"] == 3.0
    assert stats["away"]["goals_against"] == 0.0
    assert stats["home"]["position"] == stats["away"]["position"] == 1
    assert stats["home"]["points"] == stats["away"]["points"] == 7


def test_side_without_matches_is_null():
    # E only plays at home so far.
    matches = [match("E", "F", 1, 0, date(2026, 8, 1))]
    table = {"E": (5, 3)}

    away = season_stats(matches, "E", table)["away"]

    assert away["matches"] == 0
    assert away["won"] == 0
    assert away["drawn"] == 0
    assert away["lost"] == 0
    assert away["clean_sheets"] == 0
    assert away["goals_for"] is None
    assert away["goals_against"] is None
    assert away["xg_for"] is None
    assert away["shots_for"] is None
    assert away["yellow_cards"] is None
    assert away["red_cards"] is None
    assert away["btts_pct"] is None
    assert away["over_2_5_pct"] is None
    assert away["position"] == 5
    assert away["points"] == 3


def test_xg_average_ignores_missing():
    matches = [
        match("G", "H", 1, 0, date(2026, 8, 1), hxg=1.0, axg=0.5),
        match("G", "I", 2, 1, date(2026, 8, 8), hxg=2.0, axg=1.5),
        match("G", "J", 0, 0, date(2026, 8, 15)),  # no xG
        match("K", "L", 0, 0, date(2026, 8, 1)),
        match("K", "M", 0, 0, date(2026, 8, 8)),
    ]
    table = {"G": (1, 6), "K": (2, 2)}

    g = season_stats(matches, "G", table)["all"]
    k = season_stats(matches, "K", table)["all"]

    assert g["matches"] == 3
    assert g["xg_for"] == 1.5
    assert g["xg_against"] == 1.0
    assert k["xg_for"] is None
    assert k["xg_against"] is None


def test_last6_newest_first_and_points():
    matches = [
        match("A", f"Opp{day}", 1, 0, date(2026, 8, day)) for day in range(1, 7)
    ]
    # Day 7: away win 2-0 for A.
    matches.append(match("X", "A", 0, 2, date(2026, 8, 7), ay=0, ar=0, ac=2, hc=1))
    # Day 8: home loss 1-2 for A, A has yellow 2 + red 1, opponent yellow 1.
    matches.append(match("A", "Y", 1, 2, date(2026, 8, 8), hy=2, hr=1, ay=1, ar=0))
    # Day 9: not involving A, must be excluded.
    matches.append(match("B", "C", 3, 3, date(2026, 8, 9)))

    rows = last_matches(matches, "A")

    assert len(rows) == 6
    assert [r["date"] for r in rows] == [
        "2026-08-08",
        "2026-08-07",
        "2026-08-06",
        "2026-08-05",
        "2026-08-04",
        "2026-08-03",
    ]
    newest = rows[0]
    assert newest["league"] == "E0"
    assert newest["venue"] == "H"
    assert newest["opponent"] == "Y"
    assert newest["goals_for"] == 1
    assert newest["goals_against"] == 2
    assert newest["result"] == "L"
    assert newest["cards_for"] == 4  # yellow 2 + 2 × red 1
    assert newest["cards_against"] == 1

    second = rows[1]
    assert second["venue"] == "A"
    assert second["opponent"] == "X"
    assert second["goals_for"] == 2
    assert second["goals_against"] == 0
    assert second["result"] == "W"
    assert second["corners_for"] == 2
    assert second["corners_against"] == 1


def test_pair_key_is_sorted():
    assert pair_key("Chelsea", "Arsenal") == "Arsenal|Chelsea"
    assert pair_key("Arsenal", "Chelsea") == "Arsenal|Chelsea"


def test_head_to_head_both_venues_newest_first():
    matches = [
        match("Chelsea", "Arsenal", 0, 1, date(2024, 4, 2), div="E1"),
        match("Chelsea", "Arsenal", 2, 2, date(2026, 3, 1)),
        match("Arsenal", "Chelsea", 1, 0, date(2026, 10, 1), hs=12, aws=6,
              hst=5, ast=2, hc=7, ac=3, hy=1, ay=2, hr=0, ar=1),
        match("Chelsea", "Spurs", 4, 0, date(2026, 10, 20)),
    ]

    rows = head_to_head(matches, "Chelsea", "Arsenal")

    assert [r["date"] for r in rows] == ["2026-10-01", "2026-03-01", "2024-04-02"]
    newest = rows[0]
    assert newest == {
        "date": "2026-10-01",
        "league": "E0",
        "home": "Arsenal",
        "away": "Chelsea",
        "home_goals": 1,
        "away_goals": 0,
        "home_shots": 12,
        "away_shots": 6,
        "home_shots_on_target": 5,
        "away_shots_on_target": 2,
        "home_corners": 7,
        "away_corners": 3,
        "home_cards": 1,
        "away_cards": 4,  # yellow 2 + 2 × red 1
    }
    assert rows[2]["league"] == "E1"


def goals_only_match(
    home: str, away: str, hg: int, ag: int, on: date = date(2026, 8, 1), *, div: str = "NOR"
) -> Match:
    """A goals-only row: score and teams only, every stat field None."""
    return Match(
        div=div,
        season="2026",
        date=on,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        home_xg=None,
        away_xg=None,
        home_shots=None,
        away_shots=None,
        home_sot=None,
        away_sot=None,
        home_corners=None,
        away_corners=None,
        home_yellow=None,
        away_yellow=None,
        home_red=None,
        away_red=None,
    )


def test_season_stats_goals_only():
    matches = [
        goals_only_match("Bodo/Glimt", "Brann", 2, 0, date(2026, 3, 1)),
        goals_only_match("Molde", "Bodo/Glimt", 1, 1, date(2026, 3, 8)),
        goals_only_match("Bodo/Glimt", "Viking", 0, 3, date(2026, 3, 15)),
    ]
    table = league_table(matches)

    stats = season_stats(matches, "Bodo/Glimt", table)["all"]

    assert stats["matches"] == 3
    assert stats["won"] == 1
    assert stats["drawn"] == 1
    assert stats["lost"] == 1
    assert stats["points"] == 4
    assert stats["goals_for"] == pytest.approx(1.0)
    assert stats["goals_against"] == pytest.approx(1.33, abs=0.01)
    assert stats["clean_sheets"] == 1
    assert stats["btts_pct"] == pytest.approx(1 / 3, abs=0.001)
    assert stats["over_2_5_pct"] == pytest.approx(1 / 3, abs=0.001)
    for field in (
        "xg_for", "xg_against", "shots_for", "corners_for", "yellow_cards", "red_cards"
    ):
        assert stats[field] is None


def test_last_matches_goals_only():
    matches = [goals_only_match("Bodo/Glimt", "Brann", 2, 0, date(2026, 3, 1))]

    (row,) = last_matches(matches, "Bodo/Glimt")

    assert row["goals_for"] == 2
    assert row["goals_against"] == 0
    assert row["result"] == "W"
    assert row["cards_for"] is None
    assert row["cards_against"] is None
    for field in (
        "xg_for", "xg_against", "shots_for", "shots_against", "shots_on_target_for",
        "shots_on_target_against", "corners_for", "corners_against",
    ):
        assert row[field] is None


def test_head_to_head_goals_only():
    matches = [
        goals_only_match("Bodo/Glimt", "Brann", 2, 0, date(2026, 3, 1)),
        goals_only_match("Brann", "Bodo/Glimt", 1, 1, date(2026, 9, 1)),
    ]

    rows = head_to_head(matches, "Bodo/Glimt", "Brann")

    assert [(r["home_goals"], r["away_goals"]) for r in rows] == [(1, 1), (2, 0)]
    assert rows[0]["home_shots"] is None
    assert rows[0]["home_cards"] is None
    assert rows[0]["away_cards"] is None


def test_cards_property_none_when_card_counts_missing():
    match = goals_only_match("Bodo/Glimt", "Brann", 2, 0)

    assert match.home_cards is None
    assert match.away_cards is None


def test_average_skips_missing_values():
    matches = [
        match("A", "B", 1, 0, hs=10, aws=4),
        goals_only_match("A", "C", 0, 0),
    ]

    stats = season_stats(matches, "A", league_table(matches))["all"]

    assert stats["shots_for"] == 10.0
    assert stats["matches"] == 2
