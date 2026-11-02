"""Upcoming fixtures from the free feeds: fixturedownload.com for the top leagues and UEFA cups, OpenLigaDB for the DFB-Pokal."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from matchstats.leagues import LEAGUES

GERMAN_ZONE = ZoneInfo("Europe/Berlin")  # OpenLigaDB gives German local time without an offset
CUP_CODE = "DFB"
_UEFA_SLUGS = {
    "UCL": "champions-league",
    "UEL": "europa-league",
    "UECL": "conference-league",
}



@dataclass(frozen=True)
class UpcomingFixture:
    competition: str
    kickoff_utc: datetime
    home: str
    away: str


def _season_year(season: str) -> int:
    """'2627' -> 2026: the year the season starts in."""
    return 2000 + int(season[:2])


def league_fixture_urls(season: str) -> dict[str, str]:
    """fixturedownload feed of every site league that has a slug. B1 and G1 have none: their fixtures come from fixtures.csv."""
    year = _season_year(season)
    return {
        spec.code: f"https://fixturedownload.com/feed/json/{spec.fixture_slug}-{year}"
        for spec in LEAGUES
        if spec.in_site and spec.fixture_slug is not None
    }


def cup_fixture_urls(season: str) -> dict[str, str]:
    return {CUP_CODE: f"https://api.openligadb.de/getmatchdata/dfb/{_season_year(season)}"}


def uefa_fixture_urls(season: str) -> dict[str, str]:
    year = _season_year(season)
    return {code: f"https://fixturedownload.com/feed/json/{slug}-{year}" for code, slug in _UEFA_SLUGS.items()}


def parse_fixturedownload(text: str, competition: str) -> list[UpcomingFixture]:
    """Rows of a fixturedownload JSON feed: `DateUtc` is already UTC, e.g. "2026-10-27 17:30:00Z"."""
    return [
        UpcomingFixture(
            competition=competition,
            kickoff_utc=datetime.strptime(row["DateUtc"], "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=UTC),
            home=row["HomeTeam"],
            away=row["AwayTeam"],
        )
        for row in json.loads(text)
    ]


def parse_openligadb(text: str, competition: str) -> list[UpcomingFixture]:
    """Rows of an OpenLigaDB match list: `matchDateTime` is German local time without an offset."""
    return [
        UpcomingFixture(
            competition=competition,
            kickoff_utc=datetime.strptime(row["matchDateTime"], "%Y-%m-%dT%H:%M:%S")
            .replace(tzinfo=GERMAN_ZONE)
            .astimezone(UTC),
            home=row["team1"]["teamName"],
            away=row["team2"]["teamName"],
        )
        for row in json.loads(text)
    ]
