import json
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from matchstats.build import BuildError, build, validate_output
from matchstats.cli import main
from matchstats.ingest import IngestError
from matchstats.match import Match

CONTRACT_EXAMPLE = Path(__file__).parents[2] / "contract" / "example"
CURRENT = "2627"
PREVIOUS = "2526"
TODAY = date(2026, 10, 26)
LEAGUES = ["E0", "SP1", "I1", "D1", "F1", "E1", "P1"]
OPTIONAL_CODES = ["N1", "B1", "T1", "G1"]
SITE_CODES = LEAGUES + OPTIONAL_CODES
TEAMS = json.loads((Path(__file__).parent / "fixtures" / "teams_2627.json").read_text(encoding="utf-8"))

FIXTURES = (
    "Div,Date,Time,HomeTeam,AwayTeam\n"
    "E0,26/10/2026,20:00,E0 Team 00,E0 Team 01\n"
    "SP1,26/10/2026,21:00,SP1 Team 00,SP1 Team 01\n"
    "E0,27/10/2026,15:00,E0 Team 02,E0 Team 03\n"
    "D2,26/10/2026,18:00,D2 Team 00,D2 Team 01\n"
)


def synthetic_loader(short_div: str | None = None, teams: dict[str, list[str]] | None = None):
    """18 teams per division and 2 seasons; `short_div` gets only 3 teams; `teams` gives real names per division."""

    def load(divs, seasons, cache_dir, current_season):
        rng = np.random.default_rng(3)
        matches = []
        for season in (PREVIOUS, CURRENT):
            if season not in seasons:
                continue
            start = date(2025, 8, 1) if season == PREVIOUS else date(2026, 8, 1)
            for div in divs:
                names = (teams or {}).get(div) or [f"{div} Team {i:02d}" for i in range(18)]
                teams_of_div = names[:3] if div == short_div else names
                day = 0
                for home in teams_of_div:
                    for away in teams_of_div:
                        if home == away:
                            continue
                        matches.append(_match(div, season, start + timedelta(days=day % 280), home, away, rng))
                        day += 1
        return matches

    return load


def _match(div: str, season: str, when: date, home: str, away: str, rng) -> Match:
    has_xg = season == CURRENT
    return Match(
        div=div,
        season=season,
        date=when,
        home=home,
        away=away,
        home_goals=int(rng.poisson(1.4)),
        away_goals=int(rng.poisson(1.1)),
        home_xg=round(float(rng.uniform(0.2, 3.0)), 2) if has_xg else None,
        away_xg=round(float(rng.uniform(0.2, 3.0)), 2) if has_xg else None,
        home_shots=int(rng.integers(5, 25)),
        away_shots=int(rng.integers(5, 25)),
        home_sot=int(rng.integers(1, 10)),
        away_sot=int(rng.integers(1, 10)),
        home_corners=int(rng.integers(0, 14)),
        away_corners=int(rng.integers(0, 14)),
        home_yellow=int(rng.integers(0, 5)),
        away_yellow=int(rng.integers(0, 5)),
        home_red=int(rng.integers(0, 2)),
        away_red=int(rng.integers(0, 2)),
    )


HEADER_ONLY = "Div,Date,Time,HomeTeam,AwayTeam\n"
FIXTURES_HEADER = HEADER_ONLY

UPCOMING_FIXTURES = (
    "Div,Date,Time,HomeTeam,AwayTeam\n"
    "E0,25/10/2026,20:00,Yesterday Home,Yesterday Away\n"
    "E0,28/10/2026,15:00,Late Home,Late Away\n"
    "SP1,27/10/2026,21:00,SP1 Team 00,SP1 Team 01\n"
    "E0,29/10/2026,12:00,Too Late Home,Too Late Away\n"
    "D2,26/10/2026,18:00,D2 Team 00,D2 Team 01\n"
    "E0,26/10/2026,20:00,E0 Team 00,E0 Team 01\n"
)


def feed_from(texts: dict[str, object]):
    """Feed stub keyed by competition code. A value that is an exception is raised; a missing key is a 404."""

    def feed_text(name: str, url: str):
        value = texts.get(name)
        if isinstance(value, Exception):
            raise value
        return value

    return feed_text


NO_FEEDS = feed_from({})


def fd_feed(*rows: tuple[str, str, str]) -> str:
    return json.dumps(
        [{"DateUtc": when, "HomeTeam": home, "AwayTeam": away, "RoundNumber": 1} for when, home, away in rows]
    )


def dfb_feed(*rows: tuple[str, str, str]) -> str:
    return json.dumps(
        [
            {"matchDateTime": when, "team1": {"teamName": home}, "team2": {"teamName": away}}
            for when, home, away in rows
        ]
    )


def loader_with(*extra: Match):
    """The synthetic loader plus `extra` matches, for the divisions the build asks for."""
    base = synthetic_loader(teams=TEAMS)

    def load(divs, seasons, cache_dir, current_season):
        return base(divs, seasons, cache_dir, current_season) + [m for m in extra if m.div in divs]

    return load


def past_meeting(div: str, home: str, away: str) -> Match:
    return _match(div, PREVIOUS, date(2026, 3, 1), home, away, np.random.default_rng(5))


def run_build(
    out: Path,
    loader=None,
    fixtures: str = FIXTURES,
    today: date = TODAY,
    feeds=NO_FEEDS,
) -> None:
    build(
        out_dir=out,
        cache_dir=out.parent / "cache",
        today=today,
        loader=loader or synthetic_loader(),
        fixtures_text=lambda: fixtures,
        feed_text=feeds,
    )


def shape(value, key=None):
    """Recursive key structure. Team and pair names are dynamic, so their dict is shown as one '*' entry."""
    if isinstance(value, dict):
        if key in ("teams", "pairs") and value:
            return {"*": shape(next(iter(value.values())))}
        return {name: shape(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return None


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_writes_contract_files(tmp_path):
    out = tmp_path / "data"
    run_build(out)

    for code in LEAGUES:
        assert (out / "leagues" / f"{code}.json").is_file()
        assert (out / "h2h" / f"{code}.json").is_file()
    assert (out / "index.json").is_file()

    example_index = read_json(CONTRACT_EXAMPLE / "index.json")
    example_league = read_json(CONTRACT_EXAMPLE / "leagues" / "E0.json")
    example_h2h = read_json(CONTRACT_EXAMPLE / "h2h" / "E0.json")

    index = read_json(out / "index.json")
    assert [league["code"] for league in index["leagues"]] == SITE_CODES
    assert shape(index) == shape(example_index)
    assert shape(read_json(out / "leagues" / "E0.json")) == shape(example_league)
    assert shape(read_json(out / "h2h" / "E0.json")) == shape(example_h2h)


def test_today_filtered_to_top_leagues_and_date(tmp_path):
    out = tmp_path / "data"
    run_build(out)

    index = read_json(out / "index.json")
    assert index["season"] == "2026/27"
    assert index["today"] == [
        {"league": "E0", "date": "2026-10-26", "time": "20:00", "home": "E0 Team 00", "away": "E0 Team 01"},
        {"league": "SP1", "date": "2026-10-26", "time": "21:00", "home": "SP1 Team 00", "away": "SP1 Team 01"},
    ]


def test_upcoming_covers_yesterday_to_day_after_tomorrow_sorted(tmp_path):
    # Starts one Madrid day early: in the Americas "today" is still yesterday in Madrid.
    out = tmp_path / "data"
    run_build(out, fixtures=UPCOMING_FIXTURES)

    index = read_json(out / "index.json")
    assert index["upcoming"] == [
        {
            "competition": "E0", "competition_name": "Premier League", "kickoff_utc": "2026-10-25T20:00:00Z",
            "home": "Yesterday Home", "away": "Yesterday Away", "league": "E0",
        },
        {
            "competition": "E0", "competition_name": "Premier League", "kickoff_utc": "2026-10-26T20:00:00Z",
            "home": "E0 Team 00", "away": "E0 Team 01", "league": "E0",
        },
        {
            "competition": "SP1", "competition_name": "La Liga", "kickoff_utc": "2026-10-27T21:00:00Z",
            "home": "SP1 Team 00", "away": "SP1 Team 01", "league": "SP1",
        },
        {
            "competition": "E0", "competition_name": "Premier League", "kickoff_utc": "2026-10-28T15:00:00Z",
            "home": "Late Home", "away": "Late Away", "league": "E0",
        },
    ]


def test_kickoff_converted_from_uk_time(tmp_path):
    # 24/10 is still British Summer Time (UTC+1); 26/10 is GMT (UTC+0).
    fixtures = (
        "Div,Date,Time,HomeTeam,AwayTeam\n"
        "E0,26/10/2026,20:00,Gmt Home,Gmt Away\n"
        "E0,24/10/2026,20:00,Bst Home,Bst Away\n"
    )
    out = tmp_path / "data"
    run_build(out, fixtures=fixtures, today=date(2026, 10, 24))

    kickoffs = {row["home"]: row["kickoff_utc"] for row in read_json(out / "index.json")["upcoming"]}
    assert kickoffs == {"Bst Home": "2026-10-24T19:00:00Z", "Gmt Home": "2026-10-26T20:00:00Z"}


def test_league_feed_rows_use_feed_names_and_league_itself(tmp_path):
    feeds = feed_from({"E0": fd_feed(("2026-10-27 15:00:00Z", "Man Utd", "Spurs"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), feeds=feeds)

    rows = [row for row in read_json(out / "index.json")["upcoming"] if row["competition"] == "E0"]
    assert rows == [
        {
            "competition": "E0", "competition_name": "Premier League", "kickoff_utc": "2026-10-27T15:00:00Z",
            "home": "Man United", "away": "Tottenham", "league": "E0",
        }
    ]


def test_dfb_match_between_teams_of_one_league_gets_that_league(tmp_path):
    feeds = feed_from({"DFB": dfb_feed(("2026-10-27T18:00:00", "Hamburger SV", "Eintracht Frankfurt"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), feeds=feeds)

    cups = [row for row in read_json(out / "index.json")["upcoming"] if row["competition"] == "DFB"]
    assert cups == [
        {
            "competition": "DFB", "competition_name": "DFB-Pokal", "kickoff_utc": "2026-10-27T17:00:00Z",
            "home": "Hamburg", "away": "Ein Frankfurt", "league": "D1",
        }
    ]


def test_dfb_match_with_a_lower_division_team_has_no_league(tmp_path):
    feeds = feed_from({"DFB": dfb_feed(("2026-10-27T18:00:00", "SG Sonnenhof Großaspach", "FC Augsburg"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), feeds=feeds)

    cups = [row for row in read_json(out / "index.json")["upcoming"] if row["competition"] == "DFB"]
    assert cups == [
        {
            "competition": "DFB", "competition_name": "DFB-Pokal", "kickoff_utc": "2026-10-27T17:00:00Z",
            "home": "SG Sonnenhof Großaspach", "away": "Augsburg", "league": None,
        }
    ]


def test_championship_and_primeira_liga_feed_names_resolve(tmp_path):
    feeds = feed_from(
        {
            "E1": fd_feed(("2026-10-27 15:00:00Z", "Queens Park Rangers", "Birmingham City")),
            "P1": fd_feed(("2026-10-27 18:00:00Z", "Sporting CP", "SL Benfica")),
        }
    )
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    assert read_json(out / "index.json")["upcoming"] == [
        {
            "competition": "E1", "competition_name": "Championship", "kickoff_utc": "2026-10-27T15:00:00Z",
            "home": "QPR", "away": "Birmingham", "league": "E1",
        },
        {
            "competition": "P1", "competition_name": "Primeira Liga", "kickoff_utc": "2026-10-27T18:00:00Z",
            "home": "Sp Lisbon", "away": "Benfica", "league": "P1",
        },
    ]


def test_head_to_head_uses_every_division_of_the_country(tmp_path):
    out = tmp_path / "data"
    loader = loader_with(
        past_meeting("E1", "Arsenal", "Leeds"),
        past_meeting("E2", "Arsenal", "Leeds"),
        past_meeting("E0", "Burnley", "Millwall"),
    )
    run_build(out, loader=loader)

    e0_pairs = read_json(out / "h2h" / "E0.json")["pairs"]
    assert {meeting["league"] for meeting in e0_pairs["Arsenal|Leeds"]} >= {"E0", "E1", "E2"}

    e1_pairs = read_json(out / "h2h" / "E1.json")["pairs"]
    assert any(meeting["league"] == "E0" for meeting in e1_pairs["Burnley|Millwall"])


def test_validate_output_requires_the_seven_leagues_in_order(tmp_path):
    out = tmp_path / "data"
    run_build(out)
    index_path = out / "index.json"
    index = read_json(index_path)
    index["leagues"] = [league for league in index["leagues"] if league["code"] != "P1"]
    index_path.write_text(json.dumps(index), encoding="utf-8")

    problems = validate_output(out)
    assert any("leagues must be" in problem and "P1" in problem for problem in problems)


def test_failed_league_feed_falls_back_to_fixtures_csv(tmp_path):
    fixtures = "Div,Date,Time,HomeTeam,AwayTeam\nI1,27/10/2026,20:45,Milan,Inter\n"
    feeds = feed_from({"I1": IngestError("download failed after 3 attempts")})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=fixtures, feeds=feeds)

    rows = read_json(out / "index.json")["upcoming"]
    assert rows == [
        {
            "competition": "I1", "competition_name": "Serie A", "kickoff_utc": "2026-10-27T20:45:00Z",
            "home": "Milan", "away": "Inter", "league": "I1",
        }
    ]


def test_missing_league_feed_falls_back_to_fixtures_csv(tmp_path):
    fixtures = "Div,Date,Time,HomeTeam,AwayTeam\nI1,27/10/2026,20:45,Milan,Inter\n"
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=fixtures, feeds=NO_FEEDS)

    assert [row["home"] for row in read_json(out / "index.json")["upcoming"]] == ["Milan"]


def test_failing_cup_source_is_skipped_and_rest_still_builds(tmp_path, caplog):
    feeds = feed_from(
        {
            "DFB": IngestError("download failed after 3 attempts"),
            "E0": fd_feed(("2026-10-27 15:00:00Z", "Arsenal", "Chelsea")),
        }
    )
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    upcoming = read_json(out / "index.json")["upcoming"]
    assert [row["competition"] for row in upcoming] == ["E0"]
    assert "DFB" in caplog.text


def test_upcoming_sorted_by_kickoff_then_competition_order(tmp_path):
    feeds = feed_from(
        {
            "E0": fd_feed(("2026-10-27 17:00:00Z", "Chelsea", "Arsenal")),
            "DFB": dfb_feed(("2026-10-27T18:00:00", "Hamburger SV", "Eintracht Frankfurt")),
        }
    )
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures="Div,Date,Time,HomeTeam,AwayTeam\n", feeds=feeds)

    assert [row["competition"] for row in read_json(out / "index.json")["upcoming"]] == ["E0", "DFB"]


def test_ucl_match_between_teams_of_two_leagues_has_no_league(tmp_path):
    feeds = feed_from({"UCL": fd_feed(("2026-10-27 18:00:00Z", "Barcelona", "Aston Villa"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    assert read_json(out / "index.json")["upcoming"] == [
        {
            "competition": "UCL", "competition_name": "Champions League", "kickoff_utc": "2026-10-27T18:00:00Z",
            "home": "Barcelona", "away": "Aston Villa", "league": None,
        }
    ]


def test_uel_match_between_teams_of_one_league_gets_that_league(tmp_path):
    feeds = feed_from({"UEL": fd_feed(("2026-10-27 18:45:00Z", "Chelsea", "Arsenal"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    assert read_json(out / "index.json")["upcoming"] == [
        {
            "competition": "UEL", "competition_name": "Europa League", "kickoff_utc": "2026-10-27T18:45:00Z",
            "home": "Chelsea", "away": "Arsenal", "league": "E0",
        }
    ]


def test_uefa_feed_names_resolve_to_football_data_names(tmp_path):
    feeds = feed_from(
        {
            "UCL": fd_feed(("2026-10-27 18:00:00Z", "Paris", "Atleti")),
            "UEL": fd_feed(("2026-10-27 19:00:00Z", "Leipzig", "B. Dortmund")),
            "UECL": fd_feed(("2026-10-27 19:00:00Z", "Bayern München", "Braga")),
        }
    )
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    rows = read_json(out / "index.json")["upcoming"]
    assert [(row["home"], row["away"]) for row in rows] == [
        ("Paris SG", "Ath Madrid"),
        ("RB Leipzig", "Dortmund"),
        ("Bayern Munich", "Sp Braga"),
    ]


def test_paris_fc_in_ligue_1_still_resolves_to_paris_fc(tmp_path):
    feeds = feed_from({"F1": fd_feed(("2026-10-27 19:00:00Z", "Paris FC", "Lyon"))})
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    assert [row["home"] for row in read_json(out / "index.json")["upcoming"]] == ["Paris FC"]


def test_failing_uefa_feed_is_skipped_with_warning_and_rest_still_builds(tmp_path, caplog):
    feeds = feed_from(
        {
            "UECL": IngestError("download failed after 3 attempts"),
            "E0": fd_feed(("2026-10-27 15:00:00Z", "Arsenal", "Chelsea")),
        }
    )
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    upcoming = read_json(out / "index.json")["upcoming"]
    assert [row["competition"] for row in upcoming] == ["E0"]
    assert "UECL" in caplog.text


def test_uefa_rows_sort_after_leagues_and_before_dfb_at_the_same_kickoff(tmp_path):
    feeds = feed_from(
        {
            "E0": fd_feed(("2026-10-27 18:00:00Z", "Chelsea", "Arsenal")),
            "UCL": fd_feed(("2026-10-27 18:00:00Z", "Barcelona", "Aston Villa")),
            "UEL": fd_feed(("2026-10-27 18:00:00Z", "Chelsea", "Brighton")),
            "UECL": fd_feed(("2026-10-27 18:00:00Z", "Sp Braga", "Lille")),
            "DFB": dfb_feed(("2026-10-27T19:00:00", "Hamburger SV", "Eintracht Frankfurt")),
        }
    )
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS), fixtures=HEADER_ONLY, feeds=feeds)

    assert [row["competition"] for row in read_json(out / "index.json")["upcoming"]] == [
        "E0", "UCL", "UEL", "UECL", "DFB",
    ]


def test_validate_output_requires_upcoming_list(tmp_path):
    out = tmp_path / "data"
    run_build(out)
    index_path = out / "index.json"
    index = read_json(index_path)
    index["upcoming"] = "not a list"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    problems = validate_output(out)
    assert any("upcoming" in problem for problem in problems)


def test_failed_validation_keeps_previous_output(tmp_path):
    out = tmp_path / "data"
    out.mkdir()
    marker = out / "marker.txt"
    marker.write_text("previous", encoding="utf-8")

    with pytest.raises(BuildError):
        run_build(out, loader=synthetic_loader(short_div="E0"))

    assert marker.read_text(encoding="utf-8") == "previous"
    assert not (tmp_path / ".data-tmp").exists()


def test_validate_output_flags_team_missing_from_league(tmp_path):
    out = tmp_path / "data"
    run_build(out)
    assert validate_output(out) == []

    index_path = out / "index.json"
    index = read_json(index_path)
    index["leagues"][0]["teams"].append("Ghost FC")
    index_path.write_text(json.dumps(index), encoding="utf-8")

    problems = validate_output(out)
    assert any("Ghost FC" in problem for problem in problems)


def test_cli_exit_codes(tmp_path, capsys):
    good = ["build", "--out", str(tmp_path / "good" / "data"), "--cache", str(tmp_path / "cache"), "--today", "2026-10-26"]
    assert main(good, loader=synthetic_loader(), fixtures_text=lambda: FIXTURES, feed_text=NO_FEEDS) == 0
    assert (tmp_path / "good" / "data" / "index.json").is_file()

    bad = ["build", "--out", str(tmp_path / "bad" / "data"), "--cache", str(tmp_path / "cache"), "--today", "2026-10-26"]
    assert main(bad, loader=synthetic_loader(short_div="E0"), fixtures_text=lambda: FIXTURES, feed_text=NO_FEEDS) == 1
    assert "E0" in capsys.readouterr().err


NEW_TEAMS = {
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
}


def without_league(code: str):
    """The synthetic loader with no matches for `code`, as when its source has no usable data."""
    base = synthetic_loader(teams=TEAMS | NEW_TEAMS)

    def load(divs, seasons, cache_dir, current_season):
        return [m for m in base(divs, seasons, cache_dir, current_season) if m.div != code]

    return load


def index_codes(out: Path) -> list[str]:
    return [league["code"] for league in read_json(out / "index.json")["leagues"]]


def test_new_leagues_written(tmp_path):
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS | NEW_TEAMS))

    assert index_codes(out) == SITE_CODES
    example_league = read_json(CONTRACT_EXAMPLE / "leagues" / "E0.json")
    for code in OPTIONAL_CODES:
        assert (out / "leagues" / f"{code}.json").is_file()
        assert (out / "h2h" / f"{code}.json").is_file()
        assert shape(read_json(out / "leagues" / f"{code}.json")) == shape(example_league)


def test_optional_league_without_data_is_dropped(tmp_path, caplog):
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        run_build(out, loader=without_league("B1"))

    assert index_codes(out) == [code for code in SITE_CODES if code != "B1"]
    assert not (out / "leagues" / "B1.json").exists()
    assert "B1" in caplog.text


def test_optional_league_failing_validation_is_dropped(tmp_path, caplog):
    short_greece = {"G1": [f"G1 Team {i:02d}" for i in range(10)]}
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        run_build(out, loader=synthetic_loader(teams=TEAMS | short_greece))

    assert "G1" not in index_codes(out)
    assert "G1" in caplog.text


def test_required_league_still_fails_build(tmp_path):
    with pytest.raises(BuildError):
        run_build(tmp_path / "data", loader=without_league("E0"))


def test_upcoming_includes_new_league_matches(tmp_path):
    feeds = feed_from({"N1": fd_feed(("2026-10-27 15:00:00Z", "PSV", "Ajax"))})
    fixtures = FIXTURES_HEADER + "B1,27/10/2026,20:45,Anderlecht,Westerlo\n"
    out = tmp_path / "data"
    run_build(out, loader=synthetic_loader(teams=TEAMS | NEW_TEAMS), fixtures=fixtures, feeds=feeds)

    assert read_json(out / "index.json")["upcoming"] == [
        {
            "competition": "N1", "competition_name": "Eredivisie", "kickoff_utc": "2026-10-27T15:00:00Z",
            "home": "PSV Eindhoven", "away": "Ajax", "league": "N1",
        },
        {
            "competition": "B1", "competition_name": "Jupiler Pro League", "kickoff_utc": "2026-10-27T20:45:00Z",
            "home": "Anderlecht", "away": "Westerlo", "league": "B1",
        },
    ]


def test_dropped_league_row_stays_without_league(tmp_path):
    fixtures = FIXTURES_HEADER + "B1,27/10/2026,20:45,Anderlecht,Westerlo\n"
    out = tmp_path / "data"
    run_build(out, loader=without_league("B1"), fixtures=fixtures)

    assert read_json(out / "index.json")["upcoming"] == [
        {
            "competition": "B1", "competition_name": "Jupiler Pro League", "kickoff_utc": "2026-10-27T20:45:00Z",
            "home": "Anderlecht", "away": "Westerlo", "league": None,
        }
    ]


def cached_csv(div: str, teams: list[str]) -> str:
    """A football-data season CSV with one round robin of results, as the downloader caches it."""
    rows = []
    day = 0
    for home in teams:
        for away in teams:
            if home == away:
                continue
            when = date(2026, 8, 1) + timedelta(days=day % 280)
            rows.append(f"{when:%d/%m/%Y},{home},{away},1,0,10,8,4,3,5,4,2,1,0,0")
            day += 1
    return "Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR\n" + "\n".join(rows) + "\n"


def unreachable_for(divs_down: set[str]):
    """The synthetic loader, except that the given divisions fail like an unreachable source."""
    base = synthetic_loader(teams=TEAMS | NEW_TEAMS)

    def load(divs, seasons, cache_dir, current_season):
        if divs_down & set(divs):
            raise IngestError("download failed after 3 attempts")
        return base(divs, seasons, cache_dir, current_season)

    return load


def test_unreachable_optional_source_falls_back_to_cached_csv(tmp_path, caplog):
    cache = tmp_path / "cache"
    (cache / "2627").mkdir(parents=True)
    (cache / "2627" / "N1.csv").write_text(cached_csv("N1", NEW_TEAMS["N1"]), encoding="utf-8")
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        build(
            out_dir=out,
            cache_dir=cache,
            today=TODAY,
            loader=unreachable_for({"N1"}),
            fixtures_text=lambda: FIXTURES,
            feed_text=NO_FEEDS,
        )

    assert "N1" in index_codes(out)
    assert read_json(out / "h2h" / "N1.json")["pairs"]["Ajax|Feyenoord"] != []
    assert "N1" in caplog.text


def test_unreachable_optional_source_without_cache_is_dropped(tmp_path, caplog):
    out = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        run_build(out, loader=unreachable_for({"N1"}))

    assert "N1" not in index_codes(out)
    assert "N1" in caplog.text


def test_unreachable_required_source_still_fails_build(tmp_path):
    with pytest.raises(BuildError):
        run_build(tmp_path / "data", loader=unreachable_for({"E0"}))
