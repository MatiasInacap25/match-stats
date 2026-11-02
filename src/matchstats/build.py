"""Nightly build: writes the contract files for the site and validates them before publishing."""

import json
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

from matchstats.fixture_sources import (
    CUP_CODE,
    UpcomingFixture,
    cup_fixture_urls,
    league_fixture_urls,
    parse_fixturedownload,
    parse_openligadb,
    uefa_fixture_urls,
)
from matchstats.goals_model import fit_goals_model
from matchstats.ingest import (
    FIXTURES_URL,
    IngestError,
    download,
    load_matches,
    parse_fixtures_csv,
)
from matchstats.leagues import (
    COUNTRY_DIVISIONS,
    TOP_LEAGUES,
    recent_seasons,
    season_code,
    season_label,
)
from matchstats.match import Fixture, Match
from matchstats.stat_model import STAT_FIELDS, fit_stat_model
from matchstats.team_names import resolve
from matchstats.team_stats import (
    head_to_head,
    last_matches,
    league_table,
    pair_key,
    season_stats,
)

TEMP_DIR_NAME = ".data-tmp"
MIN_TEAMS = 16
GOAL_SEASONS = 3
STAT_SEASONS = 2
HEAD_TO_HEAD_SEASONS = 10
UPCOMING_DAYS = 3  # today, tomorrow and the day after, by Madrid date
UPCOMING_DAYS_BEFORE = 1  # plus yesterday: west of Madrid (the Americas) it can still be that day
KICKOFF_ZONE = ZoneInfo("Europe/London")  # football-data writes UK local kickoff times
VIEWER_ZONE = ZoneInfo("Europe/Madrid")
CUP_NAME = "DFB-Pokal"
COMPETITION_NAMES = {
    **TOP_LEAGUES,
    "UCL": "Champions League",
    "UEL": "Europa League",
    "UECL": "Conference League",
    CUP_CODE: CUP_NAME,
}
COMPETITION_ORDER = {code: position for position, code in enumerate(COMPETITION_NAMES)}

logger = logging.getLogger(__name__)

# (source name, url) -> feed text, or None when the server has no such feed.
FeedText = Callable[[str, str], str | None]


class BuildError(RuntimeError):
    pass


def build(
    out_dir: Path,
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]] = load_matches,
    fixtures_text: Callable[[], str] | None = None,
    feed_text: FeedText | None = None,
) -> None:
    """Write the contract files to a temp directory, validate them, then replace out_dir.

    On any failure the temp directory is removed and out_dir keeps its previous content.
    """
    temp_dir = out_dir.parent / TEMP_DIR_NAME
    shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        try:
            _write_files(temp_dir, cache_dir, today, loader, fixtures_text, feed_text or _cached_feed(cache_dir))
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
    feed_text: FeedText,
) -> None:
    current = season_code(today)
    divisions = list(dict.fromkeys(div for code in TOP_LEAGUES for div in COUNTRY_DIVISIONS[code]))
    matches = loader(divisions, recent_seasons(current, HEAD_TO_HEAD_SEASONS), cache_dir, current)
    fixtures = parse_fixtures_csv(_read_fixtures(cache_dir, fixtures_text))

    index_leagues = []
    for code in TOP_LEAGUES:
        top = [m for m in matches if m.div == code]
        country = [m for m in matches if m.div in COUNTRY_DIVISIONS[code]]
        league = _league_file(code, top, today, current)
        teams = sorted(league["teams"])
        _write_json(directory / "leagues" / f"{code}.json", league)
        _write_json(directory / "h2h" / f"{code}.json", {"league": code, "pairs": _head_to_head(teams, country)})
        index_leagues.append({"code": code, "name": TOP_LEAGUES[code], "teams": teams})

    known = {entry["code"]: set(entry["teams"]) for entry in index_leagues}
    index = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_label(current),
        "leagues": index_leagues,
        "today": _today_fixtures(fixtures, today),
        "upcoming": _upcoming_fixtures(fixtures, today, current, known, feed_text),
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


def _upcoming_fixtures(
    fixtures: list[Fixture],
    today: date,
    current: str,
    known: dict[str, set[str]],
    feed_text: FeedText,
) -> list[dict]:
    """League, UEFA and DFB-Pokal fixtures whose Madrid date is today-1..today+2, in UTC kickoff order.

    Each league comes from its fixturedownload feed, or from fixtures.csv when that feed fails.
    The UEFA cups (UCL, UEL, UECL) come from fixturedownload only; a failed UEFA feed is skipped.
    The DFB-Pokal comes from OpenLigaDB only; a failed cup feed is skipped. The site picks Hoy / Mañana
    by the viewer's local date, so the window is wider than two days.
    """
    found: list[UpcomingFixture] = []
    for code, url in league_fixture_urls(current).items():
        rows = _feed_rows(code, url, feed_text, parse_fixturedownload)
        if rows is None:
            logger.info("%s: using fixtures.csv instead of the feed", code)
            rows = _csv_rows(fixtures, code)
        found.extend(rows)
    for code, url in uefa_fixture_urls(current).items():
        found.extend(_feed_rows(code, url, feed_text, parse_fixturedownload) or [])
    found.extend(_feed_rows(CUP_CODE, cup_fixture_urls(current)[CUP_CODE], feed_text, parse_openligadb) or [])

    first = today - timedelta(days=UPCOMING_DAYS_BEFORE)
    last = today + timedelta(days=UPCOMING_DAYS - 1)
    rows = []
    for fixture in found:
        if not first <= fixture.kickoff_utc.astimezone(VIEWER_ZONE).date() <= last:
            continue
        entry = _upcoming_entry(fixture, known)
        sort_key = (fixture.kickoff_utc, COMPETITION_ORDER[fixture.competition], entry["home"])
        rows.append((sort_key, entry))
    rows.sort(key=lambda row: row[0])
    return [entry for _, entry in rows]


def _feed_rows(
    name: str,
    url: str,
    feed_text: FeedText,
    parse: Callable[[str, str], list[UpcomingFixture]],
) -> list[UpcomingFixture] | None:
    """Parsed rows of one source, or None when it cannot be used. A failed source is skipped, never a failed build."""
    try:
        text = feed_text(name, url)
    except IngestError as error:
        logger.warning("%s: feed skipped: %s", name, error)
        return None
    if text is None:
        logger.warning("%s: feed not found: %s", name, url)
        return None
    try:
        return parse(text, name)
    except (ValueError, KeyError, TypeError) as error:
        logger.warning("%s: feed skipped, unreadable: %s", name, error)
        return None


def _csv_rows(fixtures: list[Fixture], code: str) -> list[UpcomingFixture]:
    return [
        UpcomingFixture(competition=code, kickoff_utc=_kickoff_utc(f), home=f.home, away=f.away)
        for f in fixtures
        if f.div == code
    ]


def _upcoming_entry(fixture: UpcomingFixture, known: dict[str, set[str]]) -> dict:
    if fixture.competition in TOP_LEAGUES:
        league = fixture.competition
        home = _football_data_name(fixture.home, [league], known)
        away = _football_data_name(fixture.away, [league], known)
    else:
        league = _shared_league(fixture, known)
        scope = [league] if league is not None else list(TOP_LEAGUES)
        home = _football_data_name(fixture.home, scope, known)
        away = _football_data_name(fixture.away, scope, known)
    return {
        "competition": fixture.competition,
        "competition_name": COMPETITION_NAMES[fixture.competition],
        "kickoff_utc": fixture.kickoff_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "home": home,
        "away": away,
        "league": league,
    }


def _shared_league(fixture: UpcomingFixture, known: dict[str, set[str]]) -> str | None:
    """The one top league whose current teams include both sides; None when there is not exactly one."""
    shared = [
        code
        for code in TOP_LEAGUES
        if resolve(fixture.home, known[code]) is not None and resolve(fixture.away, known[code]) is not None
    ]
    return shared[0] if len(shared) == 1 else None


def _football_data_name(name: str, leagues: list[str], known: dict[str, set[str]]) -> str:
    """The football-data name in the first of `leagues` that knows it, else the source name."""
    for code in leagues:
        resolved = resolve(name, known[code])
        if resolved is not None:
            return resolved
    return name


def _kickoff_utc(fixture: Fixture) -> datetime:
    local = datetime.combine(
        fixture.date,
        datetime.strptime(fixture.time, "%H:%M").time(),
        tzinfo=KICKOFF_ZONE,
    )
    return local.astimezone(UTC)


def _cached_feed(cache_dir: Path) -> FeedText:
    def feed_text(name: str, url: str) -> str | None:
        return download(url, cache_dir / "fixtures" / f"{name}.json", refresh=True)

    return feed_text


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
