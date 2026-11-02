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
    load_goals_only,
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
from matchstats.uefa_strength import (
    REFERENCE,
    UEFA_SEASONS,
    UefaResult,
    completed_years,
    domestic_fits,
    parse_uefa_results,
    uefa_document,
    uefa_result_urls,
)

TEMP_DIR_NAME = ".data-tmp"
UEFA_FILE = "uefa.json"
REQUIRED_LEAGUES = [spec for spec in LEAGUES if spec.required]
# Optional site leagues are built inside a try: a league without usable data or failing its checks is dropped.
OPTIONAL_LEAGUES = [spec for spec in LEAGUES if spec.in_site and not spec.required and spec.source == "full"]
OPTIONAL_CODES = [spec.code for spec in OPTIONAL_LEAGUES]
# Data-only leagues with results and no match stats (NOR, AUT). Not in the index; UEFA rows link to them.
GOALS_ONLY_LEAGUES = [spec for spec in LEAGUES if spec.source == "goals_only"]
# Goals-only leagues whose season is one calendar year: their file says "2026", not "2026/27".
CALENDAR_SEASON_LEAGUES = frozenset({"NOR"})
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
# (country, division, cache_dir) -> matches of a goals-only league; [] when it has no usable data.
GoalsLoader = Callable[[str, str, Path], list[Match]]


class BuildError(RuntimeError):
    pass


def build(
    out_dir: Path,
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]] = load_matches,
    fixtures_text: Callable[[], str] | None = None,
    feed_text: FeedText | None = None,
    goals_loader: GoalsLoader | None = None,
) -> None:
    """Write the contract files to a temp directory, validate them, then replace out_dir.

    On any failure the temp directory is removed and out_dir keeps its previous content.
    """
    temp_dir = out_dir.parent / TEMP_DIR_NAME
    shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        try:
            _write_files(
                temp_dir,
                cache_dir,
                today,
                loader,
                goals_loader or load_goals_only,
                fixtures_text,
                feed_text or _cached_feed(cache_dir),
                previous_uefa=out_dir / UEFA_FILE,
            )
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

    # Goals-only leagues are not in the index, so their files are checked here. A dropped one has no files.
    for spec in GOALS_ONLY_LEAGUES:
        league = documents.get(f"leagues/{spec.code}.json")
        if league is not None:
            problems.extend(_spec_problems(spec, league, documents.get(f"h2h/{spec.code}.json")))

    # uefa.json is optional: a build with no usable UEFA results and no previous file has none.
    if UEFA_FILE in documents:
        problems.extend(_uefa_problems(documents[UEFA_FILE]))
    return problems


def _uefa_problems(uefa) -> list[str]:
    if not isinstance(uefa, dict):
        return [f"{UEFA_FILE}: invalid"]
    required = ("calibrated", "home_advantage", "offsets", "seasons", "backtest")
    missing = [key for key in required if key not in uefa]
    if missing:
        return [f"{UEFA_FILE}: missing {', '.join(missing)}"]
    if not isinstance(uefa["calibrated"], bool):
        return [f"{UEFA_FILE}: calibrated must be a boolean"]
    if not isinstance(uefa["offsets"], dict) or uefa["offsets"].get(REFERENCE) != {"attack": 0.0, "defense": 0.0}:
        return [f"{UEFA_FILE}: offsets must give {REFERENCE} zero attack and defense"]
    return []


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed in JSON output")


def _write_files(
    directory: Path,
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]],
    goals_loader: GoalsLoader,
    fixtures_text: Callable[[], str] | None,
    feed_text: FeedText,
    previous_uefa: Path,
) -> None:
    current = season_code(today)
    seasons = recent_seasons(current, HEAD_TO_HEAD_SEASONS)
    divisions = list(dict.fromkeys(div for spec in REQUIRED_LEAGUES for div in spec.divisions))
    matches = loader(divisions, seasons, cache_dir, current)
    fixtures = parse_fixtures_csv(_read_fixtures(cache_dir, fixtures_text))

    index_leagues = []
    # The matches of every league written, by league code: the UEFA strength model fits on them.
    league_matches: dict[str, list[Match]] = {}
    for spec in REQUIRED_LEAGUES:
        league, h2h = _league_documents(spec, matches, today, current)
        index_leagues.append(_write_league(directory, spec, league, h2h))
        league_matches[spec.code] = [m for m in matches if m.div == spec.code]
    for spec in OPTIONAL_LEAGUES:
        entry, optional_matches = _optional_league(directory, spec, loader, seasons, cache_dir, today, current)
        if entry is not None:
            index_leagues.append(entry)
            league_matches[spec.code] = optional_matches

    known = {entry["code"]: set(entry["teams"]) for entry in index_leagues}
    # Every league whose files are written: the site leagues plus the goals-only ones. UEFA rows link to these.
    data_known = dict(known)
    for spec in GOALS_ONLY_LEAGUES:
        teams, goals_matches = _goals_only_league(directory, spec, goals_loader, cache_dir, today)
        if teams is not None:
            data_known[spec.code] = teams
            league_matches[spec.code] = goals_matches
    data_known = {spec.code: data_known[spec.code] for spec in LEAGUES if spec.code in data_known}

    index = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_label(current),
        "leagues": index_leagues,
        "today": _today_fixtures(fixtures, today),
        "upcoming": _upcoming_fixtures(fixtures, today, current, known, data_known, feed_text),
    }
    _write_json(directory / "index.json", index)

    document = _uefa_document(league_matches, feed_text, current)
    if document is not None:
        _write_json(directory / UEFA_FILE, document)
    else:
        _keep_previous_uefa(directory, previous_uefa)


def uefa_report(
    cache_dir: Path,
    today: date,
    loader: Callable[..., list[Match]] = load_matches,
    feed_text: FeedText | None = None,
) -> dict | None:
    """The uefa.json object a build would write today, for `matchstats uefa-backtest`. None when no usable results."""
    current = season_code(today)
    seasons = recent_seasons(current, HEAD_TO_HEAD_SEASONS)
    full_divisions = list(dict.fromkeys(div for spec in LEAGUES if spec.source == "full" for div in spec.divisions))
    matches = loader(full_divisions, seasons, cache_dir, current)
    league_matches: dict[str, list[Match]] = {}
    for spec in LEAGUES:
        if spec.source == "full":
            league_matches[spec.code] = [m for m in matches if m.div == spec.code]
        else:
            league_matches[spec.code] = load_goals_only(spec.new_csv, spec.code, cache_dir)
    return _uefa_document(league_matches, feed_text or _cached_feed(cache_dir), current)


def _uefa_document(league_matches: dict[str, list[Match]], feed_text: FeedText, current: str) -> dict | None:
    """The uefa.json object from the past UEFA results; None when no two seasons of results are usable."""
    years = completed_years(current, UEFA_SEASONS)
    domestic = domestic_fits(league_matches, years)
    results: list[UefaResult] = []
    for year in years:
        pool = {code: set(fit["teams"]) for (code, fit_year), fit in domestic.items() if fit_year == year}
        for name, url in uefa_result_urls([year]).items():
            results.extend(_uefa_results(name, url, year, feed_text, pool))
    document = uefa_document(results, domestic)
    if document is None:
        logger.warning("%s: no usable past UEFA results", UEFA_FILE)
    return document


def _uefa_results(
    name: str, url: str, year: int, feed_text: FeedText, pool: dict[str, set[str]]
) -> list[UefaResult]:
    """Finished matches of one UEFA feed; a failed feed gives none, never a failed build."""
    try:
        text = feed_text(name, url)
    except IngestError as error:
        logger.warning("%s: feed skipped: %s", name, error)
        return []
    if text is None:
        logger.warning("%s: feed not found: %s", name, url)
        return []
    try:
        return parse_uefa_results(text, year, lambda team: _team_league(team, pool))
    except (ValueError, KeyError, TypeError) as error:
        logger.warning("%s: feed skipped, unreadable: %s", name, error)
        return []


def _keep_previous_uefa(directory: Path, previous: Path) -> None:
    """Carries the previous uefa.json over when this build has no usable one; a missing or unreadable copy is skipped."""
    if not previous.is_file():
        return
    try:
        json.loads(previous.read_bytes())
    except ValueError as error:
        logger.warning("%s: previous file unreadable, not kept: %s", UEFA_FILE, error)
        return
    shutil.copyfile(previous, directory / UEFA_FILE)


def _goals_only_league(
    directory: Path,
    spec: LeagueSpec,
    goals_loader: GoalsLoader,
    cache_dir: Path,
    today: date,
) -> tuple[set[str] | None, list[Match]]:
    """Writes a goals-only league's files; returns its teams and matches, or (None, []) when it is dropped."""
    try:
        matches = goals_loader(spec.new_csv, spec.code, cache_dir)
    except (IngestError, ValueError) as error:
        logger.warning("%s: league dropped: %s", spec.code, error)
        return None, []
    if not matches:
        logger.warning("%s: league dropped: no usable data", spec.code)
        return None, []

    league, h2h = _goals_only_documents(spec.code, matches, today)
    problems = _spec_problems(spec, league, h2h)
    if problems:
        logger.warning("%s: league dropped: %s", spec.code, "; ".join(problems))
        return None, []
    _write_json(directory / "leagues" / f"{spec.code}.json", league)
    _write_json(directory / "h2h" / f"{spec.code}.json", h2h)
    return set(league["teams"]), matches


def _goals_only_documents(code: str, matches: list[Match], today: date) -> tuple[dict, dict]:
    """The league file and head-to-head file of a goals-only league. Its current season is the newest in the file."""
    seasons = sorted({m.season for m in matches}, reverse=True)
    current = seasons[0]
    current_matches = [m for m in matches if m.season == current]
    table = league_table(current_matches)
    league = {
        "league": code,
        "season": _goals_only_season_label(code, current),
        "goals": fit_goals_model([m for m in matches if m.season in seasons[:GOAL_SEASONS]], ref_date=today),
        "teams": {
            team: {
                "season": season_stats(current_matches, team, table),
                "last6": last_matches(matches, team),
            }
            for team in sorted(table)
        },
    }
    head_to_head_matches = [m for m in matches if m.season in seasons[:HEAD_TO_HEAD_SEASONS]]
    h2h = {"league": code, "pairs": _head_to_head(sorted(league["teams"]), head_to_head_matches)}
    return league, h2h


def _goals_only_season_label(code: str, season: str) -> str:
    """'2026' stays '2026' for a calendar-year league; '2627' becomes '2026/27'."""
    return season if code in CALENDAR_SEASON_LEAGUES else season_label(season)


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
) -> tuple[dict | None, list[Match]]:
    """Writes an optional league; returns its index entry and matches, or (None, []) when it is dropped with a warning."""
    try:
        matches = _optional_matches(loader, spec, seasons, cache_dir, current)
        if not any(m.div == spec.code for m in matches):
            logger.warning("%s: league dropped: no usable data", spec.code)
            return None, []
        league, h2h = _league_documents(spec, matches, today, current)
    except ValueError as error:
        logger.warning("%s: league dropped: %s", spec.code, error)
        return None, []

    problems = _spec_problems(spec, league, h2h)
    if problems:
        logger.warning("%s: league dropped: %s", spec.code, "; ".join(problems))
        return None, []
    return _write_league(directory, spec, league, h2h), [m for m in matches if m.div == spec.code]


def _spec_problems(spec: LeagueSpec, league: dict, h2h) -> list[str]:
    """Problems of a league's files against its registry entry. An empty list means it may be written or published."""
    teams = _team_names(league)
    problems = []
    if len(teams) < spec.min_teams:
        problems.append(f"{len(teams)} teams, expected at least {spec.min_teams}")
    problems.extend(_league_problems(spec.code, teams, league, goals_only=spec.source == "goals_only"))
    problems.extend(_h2h_problems(spec.code, teams, h2h))
    return problems


def _team_names(league) -> list[str]:
    teams = _lookup(league, "teams")
    return sorted(teams) if isinstance(teams, dict) else []


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
    data_known: dict[str, set[str]],
    feed_text: FeedText,
) -> list[dict]:
    """League, UEFA and DFB-Pokal fixtures whose Madrid date is today-1..today+2, in UTC kickoff order.

    Each league comes from its fixturedownload feed, or from fixtures.csv when that feed fails.
    The UEFA cups (UCL, UEL, UECL) come from fixturedownload only; a failed UEFA feed is skipped.
    The DFB-Pokal comes from OpenLigaDB only; a failed cup feed is skipped. The site picks Hoy / Mañana
    by the viewer's local date, so the window is wider than two days.
    `known` holds the site leagues in the output; `data_known` every league written, goals-only ones included.
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
        entry = _upcoming_entry(fixture, known, data_known)
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


def _upcoming_entry(fixture: UpcomingFixture, known: dict[str, set[str]], data_known: dict[str, set[str]]) -> dict:
    """`known` and `data_known` hold only the leagues present in the output: a dropped league has no link."""
    if fixture.competition in SITE_LEAGUES:
        league = fixture.competition if fixture.competition in known else None
        scope = [league] if league is not None else []
    else:
        league = _shared_league(fixture, known)
        scope = [league] if league is not None else list(data_known)
    home = _football_data_name(fixture.home, scope, data_known)
    away = _football_data_name(fixture.away, scope, data_known)
    home_league, away_league = _team_leagues(fixture, league, data_known)
    return {
        "competition": fixture.competition,
        "competition_name": COMPETITION_NAMES[fixture.competition],
        "kickoff_utc": fixture.kickoff_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "home": home,
        "away": away,
        "league": league,
        "home_league": home_league,
        "away_league": away_league,
    }


def _team_leagues(
    fixture: UpcomingFixture, league: str | None, data_known: dict[str, set[str]]
) -> tuple[str | None, str | None]:
    """The league of each side. A league match gives its own league to both sides; DFB-Pokal gives none."""
    if fixture.competition in SITE_LEAGUES:
        return league, league
    if fixture.competition == CUP_CODE:
        return None, None
    return _team_league(fixture.home, data_known), _team_league(fixture.away, data_known)


def _team_league(name: str, data_known: dict[str, set[str]]) -> str | None:
    """The one league whose current teams contain `name`; None when no league or more than one has it."""
    codes = [code for code, teams in data_known.items() if resolve(name, teams) is not None]
    return codes[0] if len(codes) == 1 else None


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


def _league_problems(code: str, teams: list[str], league, goals_only: bool = False) -> list[str]:
    name = f"leagues/{code}.json"
    if not isinstance(league, dict):
        return [f"{name}: missing or invalid"]

    mappings = {
        "goals.teams": _lookup(league, "goals", "teams"),
        "teams": league.get("teams"),
    }
    problems = []
    if goals_only:
        if "stats" in league:
            problems.append(f"{name}: goals-only league must not have stats")
    else:
        mappings.update({f"stats.{stat}.teams": _lookup(league, "stats", stat, "teams") for stat in STAT_FIELDS})
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
