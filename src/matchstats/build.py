"""Nightly build: writes the contract files for the site and validates them before publishing."""

import json
import shutil
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

from matchstats.goals_model import fit_goals_model
from matchstats.ingest import FIXTURES_URL, IngestError, download, load_matches, parse_fixtures_csv
from matchstats.leagues import SECOND_DIVISION, TOP_LEAGUES, recent_seasons, season_code, season_label
from matchstats.match import Fixture, Match
from matchstats.stat_model import STAT_FIELDS, fit_stat_model
from matchstats.team_stats import head_to_head, last_matches, league_table, pair_key, season_stats

TEMP_DIR_NAME = ".data-tmp"
MIN_TEAMS = 16
GOAL_SEASONS = 3
STAT_SEASONS = 2
HEAD_TO_HEAD_SEASONS = 10
UPCOMING_DAYS = 3  # today, tomorrow and the day after, by Madrid date
UPCOMING_DAYS_BEFORE = 1  # plus yesterday: west of Madrid (the Americas) it can still be that day
KICKOFF_ZONE = ZoneInfo("Europe/London")  # football-data writes UK local kickoff times
VIEWER_ZONE = ZoneInfo("Europe/Madrid")


class BuildError(RuntimeError):
    pass


def build(
    out_dir: Path,
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]] = load_matches,
    fixtures_text: Callable[[], str] | None = None,
) -> None:
    """Write the contract files to a temp directory, validate them, then replace out_dir.

    On any failure the temp directory is removed and out_dir keeps its previous content.
    """
    temp_dir = out_dir.parent / TEMP_DIR_NAME
    shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        try:
            _write_files(temp_dir, cache_dir, today, loader, fixtures_text)
        except (IngestError, ValueError) as error:
            raise BuildError(str(error)) from error

        problems = validate_output(temp_dir)
        if problems:
            raise BuildError("invalid output:\n" + "\n".join(f"  {problem}" for problem in problems))

        if out_dir.exists():
            shutil.rmtree(out_dir)
        temp_dir.rename(out_dir)
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def validate_output(directory: Path) -> list[str]:
    """Problems found in a built directory. An empty list means it is valid."""
    problems: list[str] = []
    documents: dict[str, object] = {}
    for path in sorted(directory.rglob("*.json")):
        name = path.relative_to(directory).as_posix()
        try:
            documents[name] = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
        except (OSError, ValueError) as error:
            problems.append(f"{name}: not valid JSON ({error})")

    index = documents.get("index.json")
    if not isinstance(index, dict):
        return problems + ["index.json: missing or invalid"]

    leagues = index.get("leagues") or []
    codes = [entry.get("code") for entry in leagues]
    if codes != list(TOP_LEAGUES):
        problems.append(f"index.json: leagues must be {', '.join(TOP_LEAGUES)} in that order, found {codes}")
    if not isinstance(index.get("upcoming"), list):
        problems.append("index.json: upcoming must be a list")

    for entry in leagues:
        code = entry.get("code")
        teams = entry.get("teams") or []
        if len(teams) < MIN_TEAMS:
            problems.append(f"index.json: {code} has {len(teams)} teams, expected at least {MIN_TEAMS}")
        problems.extend(_league_problems(code, teams, documents.get(f"leagues/{code}.json")))
        problems.extend(_h2h_problems(code, teams, documents.get(f"h2h/{code}.json")))
    return problems


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed in JSON output")


def _write_files(
    directory: Path,
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]],
    fixtures_text: Callable[[], str] | None,
) -> None:
    current = season_code(today)
    divisions = [div for code in TOP_LEAGUES for div in (code, SECOND_DIVISION[code])]
    matches = loader(divisions, recent_seasons(current, HEAD_TO_HEAD_SEASONS), cache_dir, current)
    fixtures = parse_fixtures_csv(_read_fixtures(cache_dir, fixtures_text))

    index_leagues = []
    for code in TOP_LEAGUES:
        top = [m for m in matches if m.div == code]
        second = [m for m in matches if m.div == SECOND_DIVISION[code]]
        league = _league_file(code, top, today, current)
        teams = sorted(league["teams"])
        _write_json(directory / "leagues" / f"{code}.json", league)
        _write_json(directory / "h2h" / f"{code}.json", {"league": code, "pairs": _head_to_head(teams, top + second)})
        index_leagues.append({"code": code, "name": TOP_LEAGUES[code], "teams": teams})

    index = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_label(current),
        "leagues": index_leagues,
        "today": _today_fixtures(fixtures, today),
        "upcoming": _upcoming_fixtures(fixtures, today),
    }
    _write_json(directory / "index.json", index)


def _league_file(code: str, top: list[Match], today: date, current: str) -> dict:
    current_matches = [m for m in top if m.season == current]
    table = league_table(current_matches)
    goal_matches = [m for m in top if m.season in recent_seasons(current, GOAL_SEASONS)]
    stat_matches = [m for m in top if m.season in recent_seasons(current, STAT_SEASONS)]
    return {
        "league": code,
        "season": season_label(current),
        "goals": fit_goals_model(goal_matches, ref_date=today),
        "stats": {stat: fit_stat_model(stat_matches, stat, current) for stat in STAT_FIELDS},
        "teams": {
            team: {
                "season": season_stats(current_matches, team, table),
                "last6": last_matches(top, team),
            }
            for team in sorted(table)
        },
    }


def _head_to_head(teams: list[str], matches: list[Match]) -> dict:
    return {pair_key(a, b): head_to_head(matches, a, b) for a, b in combinations(teams, 2)}


def _today_fixtures(fixtures, today: date) -> list[dict]:
    order = {code: position for position, code in enumerate(TOP_LEAGUES)}
    selected = [f for f in fixtures if f.div in order and f.date == today]
    selected.sort(key=lambda f: (order[f.div], f.time, f.home))
    return [
        {"league": f.div, "date": f.date.isoformat(), "time": f.time, "home": f.home, "away": f.away}
        for f in selected
    ]


def _upcoming_fixtures(fixtures: list[Fixture], today: date) -> list[dict]:
    """Top-league fixtures whose Madrid date is today-1..today+2, in UTC kickoff order.

    The site picks Hoy / Mañana by the viewer's local date, so the window is wider than two days.
    """
    order = {code: position for position, code in enumerate(TOP_LEAGUES)}
    first = today - timedelta(days=UPCOMING_DAYS_BEFORE)
    last = today + timedelta(days=UPCOMING_DAYS - 1)
    rows = []
    for fixture in fixtures:
        if fixture.div not in order:
            continue
        kickoff = _kickoff_utc(fixture)
        if not first <= kickoff.astimezone(VIEWER_ZONE).date() <= last:
            continue
        entry = {
            "league": fixture.div,
            "kickoff_utc": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home": fixture.home,
            "away": fixture.away,
        }
        rows.append(((kickoff, order[fixture.div], fixture.home), entry))
    rows.sort(key=lambda row: row[0])
    return [entry for _, entry in rows]


def _kickoff_utc(fixture: Fixture) -> datetime:
    local = datetime.combine(
        fixture.date,
        datetime.strptime(fixture.time, "%H:%M").time(),
        tzinfo=KICKOFF_ZONE,
    )
    return local.astimezone(timezone.utc)


def _read_fixtures(cache_dir: Path, fixtures_text: Callable[[], str] | None) -> str:
    if fixtures_text is not None:
        return fixtures_text()
    text = download(FIXTURES_URL, cache_dir / "fixtures.csv", refresh=True)
    if text is None:
        raise BuildError(f"fixtures not found: {FIXTURES_URL}")
    return text


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, allow_nan=False, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def _lookup(value, *keys):
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _league_problems(code: str, teams: list[str], league) -> list[str]:
    name = f"leagues/{code}.json"
    if not isinstance(league, dict):
        return [f"{name}: missing or invalid"]

    mappings = {
        "goals.teams": _lookup(league, "goals", "teams"),
        "teams": league.get("teams"),
        **{f"stats.{stat}.teams": _lookup(league, "stats", stat, "teams") for stat in STAT_FIELDS},
    }
    problems = []
    for where, mapping in mappings.items():
        if not isinstance(mapping, dict):
            problems.append(f"{name}: {where} missing")
            continue
        problems.extend(f"{name}: {team} missing from {where}" for team in teams if team not in mapping)
    return problems


def _h2h_problems(code: str, teams: list[str], h2h) -> list[str]:
    name = f"h2h/{code}.json"
    pairs = _lookup(h2h, "pairs")
    if not isinstance(pairs, dict):
        return [f"{name}: missing or invalid"]

    expected = {pair_key(a, b) for a, b in combinations(teams, 2)}
    problems = []
    if len(pairs) != len(expected):
        problems.append(f"{name}: {len(pairs)} pairs, expected {len(expected)}")
    problems.extend(f"{name}: pair {key} missing" for key in sorted(expected - set(pairs)))
    return problems
