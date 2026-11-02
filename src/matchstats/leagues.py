from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class LeagueSpec:
    code: str  # "N1", "NOR"
    name: str  # "Eredivisie"
    divisions: tuple[str, ...]  # head-to-head divisions, top first
    source: Literal["full", "goals_only"]
    min_teams: int
    in_site: bool  # full league in the site: chip, calendar, comparator
    required: bool  # True only for the original 7
    fixture_slug: str | None  # fixturedownload slug; None -> fixtures.csv
    new_csv: str | None  # football-data "new/<CODE>.csv" for goals-only leagues


# Order is the site order (in_site leagues first), then the data-only leagues.
LEAGUES: tuple[LeagueSpec, ...] = (
    LeagueSpec("E0", "Premier League", ("E0", "E1", "E2"), "full", 16, True, True, "epl", None),
    LeagueSpec("SP1", "La Liga", ("SP1", "SP2"), "full", 16, True, True, "la-liga", None),
    LeagueSpec("I1", "Serie A", ("I1", "I2"), "full", 16, True, True, "serie-a", None),
    LeagueSpec("D1", "Bundesliga", ("D1", "D2"), "full", 16, True, True, "bundesliga", None),
    LeagueSpec("F1", "Ligue 1", ("F1", "F2"), "full", 16, True, True, "ligue-1", None),
    LeagueSpec("E1", "Championship", ("E0", "E1", "E2"), "full", 16, True, True, "championship", None),
    LeagueSpec("P1", "Primeira Liga", ("P1",), "full", 16, True, True, "primeira-liga", None),
    LeagueSpec("N1", "Eredivisie", ("N1",), "full", 16, True, False, "eredivisie", None),
    LeagueSpec("B1", "Jupiler Pro League", ("B1",), "full", 16, True, False, None, None),
    LeagueSpec("T1", "Süper Lig", ("T1",), "full", 16, True, False, "super-lig", None),
    LeagueSpec("G1", "Super League Greece", ("G1",), "full", 14, True, False, None, None),
    LeagueSpec("NOR", "Eliteserien", ("NOR",), "goals_only", 16, False, False, None, "NOR"),
    LeagueSpec("AUT", "Austrian Bundesliga", ("AUT",), "goals_only", 12, False, False, None, "AUT"),
)

TOP_LEAGUES: dict[str, str] = {spec.code: spec.name for spec in LEAGUES if spec.required}
SITE_LEAGUES: dict[str, str] = {spec.code: spec.name for spec in LEAGUES if spec.in_site}
DATA_LEAGUES: dict[str, str] = {spec.code: spec.name for spec in LEAGUES}

# League -> every division of its country, top first, for the 7 required leagues. Head to head uses all of them,
# since teams move between divisions. The other leagues carry their divisions on their LeagueSpec.
COUNTRY_DIVISIONS: dict[str, tuple[str, ...]] = {spec.code: spec.divisions for spec in LEAGUES if spec.required}


def season_code(d: date) -> str:
    """Season code for a date. Seasons start on July 1: 2026-07-01 is '2627'."""
    start_year = d.year if d.month >= 7 else d.year - 1
    return _code(start_year)


def season_label(code: str) -> str:
    """'2627' -> '2026/27'."""
    return f"20{code[:2]}/{code[2:]}"


def recent_seasons(current: str, n: int) -> list[str]:
    """The current season and the n-1 before it, newest first."""
    start_year = 2000 + int(current[:2])
    return [_code(start_year - i) for i in range(n)]


def _code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"
