import json
from pathlib import Path

import pytest

from matchstats.team_names import ALIASES, normalize, resolve

FIXTURES = Path(__file__).parent / "fixtures"
CURRENT_TEAMS: dict[str, list[str]] = json.loads((FIXTURES / "teams_2627.json").read_text(encoding="utf-8"))
SAMPLE_LEAGUES = {
    "I1": "fd_serie-a-2026_sample.json",
    "D1": "fd_bundesliga-2026_sample.json",
    "E1": "fd_championship-2026_sample.json",
    "P1": "fd_primeira-liga-2026_sample.json",
}

# Team names from the fixturedownload feeds for the leagues whose samples are not recorded.
# Kept inline so every top-5 league is covered without storing more fixtures.
EXTRA_FEED_TEAMS = {
    "E0": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea", "Coventry",
        "Crystal Palace", "Everton", "Fulham", "Hull", "Ipswich", "Leeds", "Liverpool", "Man City",
        "Man Utd", "Newcastle", "Nott'm Forest", "Spurs", "Sunderland",
    ],
    "SP1": [
        "Athletic Club", "Atlético de Madrid", "CA Osasuna", "Celta", "Deportivo Alavés", "Elche CF",
        "FC Barcelona", "Getafe CF", "Levante UD", "Málaga CF", "R. Racing Club", "RC Deportivo",
        "RCD Espanyol de Barcelona", "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad",
        "Sevilla FC", "Valencia CF", "Villarreal CF",
    ],
    "F1": [
        "AJ Auxerre", "AS Monaco", "Angers SCO", "Estac Troyes", "FC Lorient", "Havre Athletic Club",
        "LOSC Lille", "Le Mans FC", "OGC Nice", "Olympique Lyonnais", "Olympique de Marseille",
        "Paris FC", "Paris Saint-Germain", "RC Lens", "RC Strasbourg Alsace", "Stade Brestois 29",
        "Stade Rennais FC", "Toulouse FC",
    ],
    "N1": [
        "ADO Den Haag", "AZ", "Ajax", "Excelsior Rotterdam", "FC Groningen", "FC Twente", "FC Utrecht",
        "Feyenoord", "Fortuna Sittard", "Go Ahead Eagles", "N.E.C. Nijmegen", "PEC Zwolle", "PSV",
        "SC Cambuur", "Sparta Rotterdam", "Telstar", "Willem II", "sc Heerenveen",
    ],
    "T1": [
        "Alanyaspor", "Amedspor", "Besiktas", "Erzurumspor", "Eyüpspor", "Fenerbahçe", "Galatasaray",
        "Gaziantep", "Gençlerbirligi", "Göztepe", "Istanbul Basaksehir", "Kasimpasa", "Kocaelispor",
        "Konyaspor", "Samsunspor", "Trabzonspor", "Çaykur Rizespor", "Çorum",
    ],
}

# football-data.co.uk names of the new leagues, from their 2026/27 season files. B1 and G1 have no feed of their own.
NEW_LEAGUE_TEAMS: dict[str, list[str]] = {
    "N1": [
        "AZ Alkmaar", "Ajax", "Cambuur", "Den Haag", "Excelsior", "Feyenoord", "For Sittard",
        "Go Ahead Eagles", "Groningen", "Heerenveen", "Nijmegen", "PSV Eindhoven", "Sparta Rotterdam",
        "Telstar", "Twente", "Utrecht", "Willem II", "Zwolle",
    ],
    "B1": [
        "Anderlecht", "Antwerp", "Beveren", "Cercle Brugge", "Charleroi", "Club Brugge", "Genk", "Gent",
        "Kortrijk", "Lommel SK", "Mechelen", "Oud-Heverlee Leuven", "RAAL La Louviere", "St Truiden",
        "St. Gilloise", "Standard", "Waregem", "Westerlo",
    ],
    "T1": [
        "Alanyaspor", "Amedspor", "Besiktas", "Buyuksehyr", "Corum", "Erzurumspor", "Eyupspor", "Fenerbahce",
        "Galatasaray", "Gaziantep", "Genclerbirligi", "Goztep", "Kasimpasa", "Kocaelispor", "Konyaspor",
        "Rizespor", "Samsunspor", "Trabzonspor",
    ],
    "G1": [
        "AEK", "Aris", "Asteras Tripolis", "Atromitos", "Iraklis", "Kalamata", "Kifisia", "Levadeiakos",
        "OFI Crete", "Olympiakos", "PAOK", "Panathinaikos", "Panetolikos", "Volos NFC",
    ],
    # Goals-only leagues: teams of their newest season in the file (NOR 2026, AUT 2026/2027).
    "NOR": [
        "Aalesund", "Bodo/Glimt", "Brann", "Fredrikstad", "HamKam", "KFUM Oslo", "Kristiansund", "Lillestrom",
        "Molde", "Rosenborg", "Sandefjord", "Sarpsborg 08", "Start", "Tromso", "Valerenga", "Viking",
    ],
    "AUT": [
        "A. Lustenau", "Altach", "Austria Vienna", "Grazer AK", "Hartberg", "LASK", "Ried", "SK Rapid",
        "Salzburg", "Sturm Graz", "Tirol", "Wolfsberger AC",
    ],
}
ALL_CURRENT_TEAMS: dict[str, list[str]] = {**CURRENT_TEAMS, **NEW_LEAGUE_TEAMS}

# UEFA feed names (2026 UCL, UEL and UECL feeds) of teams in one of our leagues -> that league.
UEFA_FEED_LEAGUES: dict[str, str] = {
    "Bodø/Glimt": "NOR",
    "Lillestrøm": "NOR",
    "Viking": "NOR",
    "Brann": "NOR",
    "LASK": "AUT",
    "Salzburg": "AUT",
    "Sturm Graz": "AUT",
    "PSV": "N1",
    "AZ": "N1",
    "N.E.C.": "N1",
    "Feyenoord": "N1",
    "Twente": "N1",
    "Club Brugge": "B1",
    "Anderlecht": "B1",
    "Gent": "B1",
    "Sint-Truidense": "B1",
    "Galatasaray": "T1",
    "Fenerbahçe": "T1",
    "Besiktas": "T1",
    "Trabzonspor": "T1",
    "Olympiacos": "G1",
    "AEK Athens": "G1",
    "Panathinaikos": "G1",
    "OFI Crete": "G1",
}


def feed_team_names(filename: str) -> set[str]:
    matches = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    return {m["HomeTeam"] for m in matches} | {m["AwayTeam"] for m in matches}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Atlético de Madrid", "atletico madrid"),
        ("1. FC Köln", "koln"),
        ("FC Schalke 04", "schalke"),
        ("SC Paderborn 07", "paderborn"),
        ("Sport-Club Freiburg", "sport club freiburg"),
        ("Nott'm Forest", "nott m forest"),
        ("Stade Rennais FC", "rennais"),
    ],
)
def test_normalize_drops_legal_tokens_accents_and_digits(raw, expected):
    assert normalize(raw) == expected


def test_normalize_is_case_insensitive_and_ignores_spacing():
    assert normalize("  MAN   united ") == normalize("Man United") == "man united"


def test_resolve_uses_alias_when_target_is_known():
    assert resolve("Man Utd", {"Man United", "Arsenal"}) == "Man United"


def test_resolve_returns_none_when_alias_target_is_not_in_known_set():
    # "Man Utd" belongs to the Premier League; it must not resolve inside a Bundesliga set.
    assert resolve("Man Utd", {"Augsburg"}) is None


def test_resolve_matches_unique_normalized_name():
    assert resolve("FC Augsburg", {"Augsburg", "Hamburg"}) == "Augsburg"


def test_resolve_returns_none_when_normalized_match_is_ambiguous():
    assert resolve("Foo FC", {"Foo SC", "FC Foo"}) is None


def test_resolve_returns_none_for_unknown_team():
    assert resolve("Wolverhampton", {"Arsenal"}) is None


@pytest.mark.parametrize("league", sorted(SAMPLE_LEAGUES))
def test_every_team_in_recorded_league_sample_resolves(league):
    known = set(CURRENT_TEAMS[league])
    unresolved = sorted(name for name in feed_team_names(SAMPLE_LEAGUES[league]) if resolve(name, known) is None)
    assert unresolved == []


@pytest.mark.parametrize("league", sorted(EXTRA_FEED_TEAMS))
def test_every_team_in_other_top_league_feed_resolves(league):
    known = set(ALL_CURRENT_TEAMS[league])
    unresolved = sorted(name for name in EXTRA_FEED_TEAMS[league] if resolve(name, known) is None)
    assert unresolved == []


@pytest.mark.parametrize(("name", "league"), sorted(UEFA_FEED_LEAGUES.items()))
def test_uefa_feed_name_resolves_in_its_league_only(name, league):
    leagues = [code for code, teams in ALL_CURRENT_TEAMS.items() if resolve(name, set(teams)) is not None]
    assert leagues == [league]


def test_uefa_name_outside_our_leagues_resolves_nowhere():
    # Shakhtar plays in no league we build, so no league may claim it.
    assert [code for code, teams in ALL_CURRENT_TEAMS.items() if resolve("Shakhtar", set(teams)) is not None] == []


def test_every_alias_targets_a_current_team():
    current = {team for teams in ALL_CURRENT_TEAMS.values() for team in teams}
    assert sorted(target for target in set(ALIASES.values()) if target not in current) == []
