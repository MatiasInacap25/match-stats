import json
from datetime import UTC, datetime
from pathlib import Path

from matchstats.fixture_sources import (
    UpcomingFixture,
    cup_fixture_urls,
    league_fixture_urls,
    parse_fixturedownload,
    parse_openligadb,
    uefa_fixture_urls,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_league_fixture_urls_use_season_year_and_nine_league_slugs():
    # B1 and G1 have no fixturedownload slug: their fixtures come from fixtures.csv only.
    assert league_fixture_urls("2627") == {
        "E0": "https://fixturedownload.com/feed/json/epl-2026",
        "SP1": "https://fixturedownload.com/feed/json/la-liga-2026",
        "I1": "https://fixturedownload.com/feed/json/serie-a-2026",
        "D1": "https://fixturedownload.com/feed/json/bundesliga-2026",
        "F1": "https://fixturedownload.com/feed/json/ligue-1-2026",
        "E1": "https://fixturedownload.com/feed/json/championship-2026",
        "P1": "https://fixturedownload.com/feed/json/primeira-liga-2026",
        "N1": "https://fixturedownload.com/feed/json/eredivisie-2026",
        "T1": "https://fixturedownload.com/feed/json/super-lig-2026",
    }


def test_cup_fixture_urls_point_to_dfb_pokal_for_the_season_year():
    assert cup_fixture_urls("2627") == {"DFB": "https://api.openligadb.de/getmatchdata/dfb/2026"}


def test_uefa_fixture_urls_use_season_year_and_three_competition_slugs():
    assert uefa_fixture_urls("2627") == {
        "UCL": "https://fixturedownload.com/feed/json/champions-league-2026",
        "UEL": "https://fixturedownload.com/feed/json/europa-league-2026",
        "UECL": "https://fixturedownload.com/feed/json/conference-league-2026",
    }


def test_parse_fixturedownload_reads_utc_dates_and_names():
    text = json.dumps(
        [{"DateUtc": "2026-10-27 17:30:00Z", "HomeTeam": "Sassuolo", "AwayTeam": "Lazio", "RoundNumber": 9}]
    )

    assert parse_fixturedownload(text, "I1") == [
        UpcomingFixture(
            competition="I1",
            kickoff_utc=datetime(2026, 10, 27, 17, 30, tzinfo=UTC),
            home="Sassuolo",
            away="Lazio",
        )
    ]


def test_parse_fixturedownload_recorded_sample_has_every_round_match():
    rows = parse_fixturedownload(read("fd_serie-a-2026_sample.json"), "I1")

    assert len(rows) == 40
    assert all(row.competition == "I1" for row in rows)
    assert all(row.kickoff_utc.tzinfo is UTC for row in rows)


def test_parse_fixturedownload_recorded_championship_sample_has_every_round_match():
    rows = parse_fixturedownload(read("fd_championship-2026_sample.json"), "E1")

    assert len(rows) == 552  # 24 teams, home and away
    assert all(row.competition == "E1" for row in rows)


def test_parse_fixturedownload_recorded_primeira_liga_sample_has_every_round_match():
    rows = parse_fixturedownload(read("fd_primeira-liga-2026_sample.json"), "P1")

    assert len(rows) == 306  # 18 teams, home and away
    assert all(row.competition == "P1" for row in rows)


def test_parse_openligadb_converts_berlin_winter_time_to_utc():
    text = json.dumps(
        [{"matchDateTime": "2026-10-27T18:00:00", "team1": {"teamName": "A"}, "team2": {"teamName": "B"}}]
    )

    (row,) = parse_openligadb(text, "DFB")
    assert row.kickoff_utc == datetime(2026, 10, 27, 17, 0, tzinfo=UTC)


def test_parse_openligadb_converts_berlin_summer_time_to_utc():
    text = json.dumps(
        [{"matchDateTime": "2026-08-21T18:00:00", "team1": {"teamName": "A"}, "team2": {"teamName": "B"}}]
    )

    (row,) = parse_openligadb(text, "DFB")
    assert row.kickoff_utc == datetime(2026, 8, 21, 16, 0, tzinfo=UTC)


def test_parse_openligadb_recorded_sample_keeps_source_names_and_competition():
    rows = parse_openligadb(read("openligadb_dfb_2026_sample.json"), "DFB")

    assert len(rows) == 48
    hamburg = [row for row in rows if row.home == "Hamburger SV"]
    assert hamburg == [
        UpcomingFixture(
            competition="DFB",
            kickoff_utc=datetime(2026, 10, 27, 17, 0, tzinfo=UTC),
            home="Hamburger SV",
            away="Eintracht Frankfurt",
        )
    ]
