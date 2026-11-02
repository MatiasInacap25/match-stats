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
    parse_season_csv,
    season_url,
)
from matchstats.leagues import (
    LEAGUES,
    SITE_LEAGUES,
    TOP_LEAGUES,
    LeagueSpec,
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
REQUIRED_LEAGUES = [spec for spec in LEAGUES if spec.required]
# Optional site leagues are built inside a try: a league without usable data or failing its checks is dropped.
OPTIONAL_LEAGUES = [spec for spec in LEAGUES if spec.in_site and not spec.required and spec.source == "full"]
OPTIONAL_CODES = [spec.code for spec in OPTIONAL_LEAGUES]
SPECS = {spec.code: spec for spec in LEAGUES}
GOAL_SEASONS = 3
STAT_SEASONS = 2
HEAD_TO_HEAD_SEASONS = 10
UPCOMING_DAYS = 3  # today, tomorrow and the day after, by Madrid date
UPCOMING_DAYS_BEFORE = 1  # plus yesterday: west of Madrid (the Americas) it can still be that day
KICKOFF_ZONE = ZoneInfo("Europe/London")  # football-data writes UK local kickoff times
VIEWER_ZONE = ZoneInfo("Europe/Madrid")
CUP_NAME = "DFB-Pokal"
COMPETITION_NAMES = {
    **SITE_LEAGUES,
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
    required_codes, optional_codes = codes[: len(TOP_LEAGUES)], codes[len(TOP_LEAGUES) :]
    if required_codes != list(TOP_LEAGUES) or optional_codes != [c for c in OPTIONAL_CODES if c in optional_codes]:
        problems.append(
            f"index.json: leagues must be {', '.join(TOP_LEAGUES)}, then optional leagues in order "
            f"({', '.join(OPTIONAL_CODES)}), found {codes}"
        )
    if not isinstance(index.get("upcoming"), list):
        problems.append("index.json: upcoming must be a list")

    for entry in leagues:
        code = entry.get("code")
        teams = entry.get("teams") or []
        spec = SPECS.get(code)
        minimum = spec.min_teams if spec is not None else 0
        if len(teams) < minimum:
            problems.append(f"index.json: {code} has {len(teams)} teams, expected at least {minimum}")
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
    seasons = recent_seasons(current, HEAD_TO_HEAD_SEASONS)
    divisions = list(dict.fromkeys(div for spec in REQUIRED_LEAGUES for div in spec.divisions))
    matches = loader(divisions, seasons, cache_dir, current)
    fixtures = parse_fixtures_csv(_read_fixtures(cache_dir, fixtures_text))

    index_leagues = []
    for spec in REQUIRED_LEAGUES:
        league, h2h = _league_documents(spec, matches, today, current)
        index_leagues.append(_write_league(directory, spec, league, h2h))
    for spec in OPTIONAL_LEAGUES:
        entry = _optional_league(directory, spec, loader, seasons, cache_dir, today, current)
        if entry is not None:
            index_leagues.append(entry)

    known = {entry["code"]: set(entry["teams"]) for entry in index_leagues}
    index = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_label(current),
        "leagues": index_leagues,
        "today": _today_fixtures(fixtures, today),
        "upcoming": _upcoming_fixtures(fixtures, today, current, known, feed_text),
    }
    _write_json(directory / "index.json", index)


def _league_documents(spec: LeagueSpec, matches: list[Match], today: date, current: str) -> tuple[dict, dict]:
    """The league file and the head-to-head file of one league, from the matches of its divisions."""
    top = [m for m in matches if m.div == spec.code]
    country = [m for m in matches if m.div in spec.divisions]
    league = _league_file(spec.code, top, today, current)
    return league, {"league": spec.code, "pairs": _head_to_head(sorted(league["teams"]), country)}


def _write_league(directory: Path, spec: LeagueSpec, league: dict, h2h: dict) -> dict:
    _write_json(directory / "leagues" / f"{spec.code}.json", league)
    _write_json(directory / "h2h" / f"{spec.code}.json", h2h)
    return {"code": spec.code, "name": spec.name, "teams": sorted(league["teams"])}


def _optional_league(
    directory: Path,
    spec: LeagueSpec,
    loader: Callable[..., list[Match]],
    seasons: list[str],
    cache_dir: Path,
    today: date,
    current: str,
) -> dict | None:
    """Writes an optional league and returns its index entry; None when it is dropped with a warning."""
    try:
        matches = _optional_matches(loader, spec, seasons, cache_dir, current)
        if not any(m.div == spec.code for m in matches):
            logger.warning("%s: league dropped: no usable data", spec.code)
            return None
        league, h2h = _league_documents(spec, matches, today, current)
    except ValueError as error:
        logger.warning("%s: league dropped: %s", spec.code, error)
        return None

    problems = _optional_problems(spec, league, h2h)
    if problems:
        logger.warning("%s: league dropped: %s", spec.code, "; ".join(problems))
        return None
    return _write_league(directory, spec, league, h2h)


def _optional_problems(spec: LeagueSpec, league: dict, h2h: dict) -> list[str]:
    teams = sorted(league["teams"])
    problems = []
    if len(teams) < spec.min_teams:
        problems.append(f"{len(teams)} teams, expected at least {spec.min_teams}")
    problems.extend(_league_problems(spec.code, teams, league))
    problems.extend(_h2h_problems(spec.code, teams, h2h))
    return problems


def _optional_matches(
    loader: Callable[..., list[Match]],
    spec: LeagueSpec,
    seasons: list[str],
    cache_dir: Path,
    current: str,
) -> list[Match]:
    """Matches of an optional league. An unreachable source falls back to the cached CSVs it already has."""
    try:
        return loader(list(spec.divisions), seasons, cache_dir, current)
    except IngestError as error:
        logger.warning("%s: source unreachable, using cached CSVs: %s", spec.code, error)
    return _cached_matches(spec.divisions, seasons, cache_dir)


def _cached_matches(divisions: tuple[str, ...], seasons: list[str], cache_dir: Path) -> list[Match]:
    matches = []
    for season in seasons:
        for div in divisions:
            cache_file = cache_dir / season / f"{div}.csv"
            if not cache_file.exists():
                continue
            text = download(season_url(season, div), cache_file, refresh=False)
            if text is None:
                continue
            try:
                matches.extend(parse_season_csv(text, div, season))
            except IngestError as error:
                logger.warning("%s %s: cached CSV skipped: %s", div, season, error)
    return matches


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
    feeds = league_fixture_urls(current)
    for code in SITE_LEAGUES:
        url = feeds.get(code)
        if url is None:
            found.extend(_csv_rows(fixtures, code))
            continue
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
    """`known` holds only the leagues present in the output: a league dropped by the build has no link."""
    if fixture.competition in SITE_LEAGUES:
        league = fixture.competition if fixture.competition in known else None
        scope = [league] if league is not None else []
    else:
        league = _shared_league(fixture, known)
        scope = [league] if league is not None else list(known)
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
    """The one site league whose current teams include both sides; None when there is not exactly one."""
    shared = [
        code
        for code, teams in known.items()
        if resolve(fixture.home, teams) is not None and resolve(fixture.away, teams) is not None
    ]
    return shared[0] if len(shared) == 1 else None


def _football_data_name(name: str, leagues: list[str], known: dict[str, set[str]]) -> str:
    """The football-data name in the first of `leagues` that knows it, else the source name."""
    for code in leagues:
        resolved = resolve(name, known.get(code, set()))
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
