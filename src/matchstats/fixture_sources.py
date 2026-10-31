"""Upcoming fixtures from the free feeds: fixturedownload.com for the top leagues, OpenLigaDB for the DFB-Pokal."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

GERMAN_ZONE = ZoneInfo("Europe/Berlin")  # OpenLigaDB gives German local time without an offset
CUP_CODE = "DFB"

_LEAGUE_SLUGS = {
    "E0": "epl",
    "SP1": "la-liga",
    "I1": "serie-a",
    "D1": "bundesliga",
    "F1": "ligue-1",
    "E1": "championship",
    "P1": "primeira-liga",
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
    year = _season_year(season)
    return {code: f"https://fixturedownload.com/feed/json/{slug}-{year}" for code, slug in _LEAGUE_SLUGS.items()}


def cup_fixture_urls(season: str) -> dict[str, str]:
    return {CUP_CODE: f"https://api.openligadb.de/getmatchdata/dfb/{_season_year(season)}"}


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
