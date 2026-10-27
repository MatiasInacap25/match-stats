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
LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]
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
    assert [league["code"] for league in index["leagues"]] == LEAGUES
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
