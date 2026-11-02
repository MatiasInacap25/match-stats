import csv
import io
import logging
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from matchstats.match import Fixture, Match

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
_SEASON_BASE_URL = "https://www.football-data.co.uk/mmz4281"
_GOALS_ONLY_BASE_URL = "https://www.football-data.co.uk/new"
USER_AGENT = "matchstats/0.1"
TIMEOUT_SECONDS = 30
ATTEMPTS = 3
BACKOFF_SECONDS = 2
PAUSE_SECONDS = 1

logger = logging.getLogger(__name__)

_SEASON_COLUMNS = (
    "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG",
    "HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR",
)
_FIXTURE_COLUMNS = ("Div", "Date", "Time", "HomeTeam", "AwayTeam")
_GOALS_ONLY_COLUMNS = ("Season", "Date", "Home", "Away", "HG", "AG")


class IngestError(RuntimeError):
    pass


def season_url(code: str, div: str) -> str:
    return f"{_SEASON_BASE_URL}/{code}/{div}.csv"


def parse_season_csv(text: str, div: str, season: str) -> list[Match]:
    reader = csv.DictReader(io.StringIO(_strip_bom(text)))
    _require_columns(reader.fieldnames, _SEASON_COLUMNS, f"{div} {season}")

    matches = []
    for row in reader:
        # Rows without a result (postponed or not yet played) are not matches yet.
        if not row["FTHG"].strip() or not row["FTAG"].strip():
            continue
        where = f"{div} {season} {row['Date']} {row['HomeTeam']} v {row['AwayTeam']}"
        stats = _count_stats(row, where)
        if stats is None:
            continue
        matches.append(
            Match(
                div=div,
                season=season,
                date=_parse_date(row["Date"], where),
                home=row["HomeTeam"],
                away=row["AwayTeam"],
                home_goals=_int(row, "FTHG", where),
                away_goals=_int(row, "FTAG", where),
                home_xg=_optional_float(row, "HxG", where),
                away_xg=_optional_float(row, "AxG", where),
                **stats,
            )
        )
    return matches


def parse_fixtures_csv(text: str) -> list[Fixture]:
    reader = csv.DictReader(io.StringIO(_strip_bom(text)))
    _require_columns(reader.fieldnames, _FIXTURE_COLUMNS, "fixtures")

    fixtures = []
    for row in reader:
        where = f"fixture {row['Div']} {row['Date']} {row['HomeTeam']} v {row['AwayTeam']}"
        fixtures.append(
            Fixture(
                div=row["Div"],
                date=_parse_date(row["Date"], where),
                time=row["Time"],
                home=row["HomeTeam"],
                away=row["AwayTeam"],
            )
        )
    return fixtures


def goals_only_url(country: str) -> str:
    return f"{_GOALS_ONLY_BASE_URL}/{country}.csv"


def parse_goals_only_csv(text: str, div: str) -> list[Match]:
    """Results-only leagues (football-data `new/<CC>.csv`): score and teams, no match stats."""
    reader = csv.DictReader(io.StringIO(_strip_bom(text)))
    _require_columns(reader.fieldnames, _GOALS_ONLY_COLUMNS, div)

    matches = []
    for row in reader:
        # Rows without a final score are not matches yet.
        if not row["HG"].strip() or not row["AG"].strip():
            continue
        where = f"{div} {row['Date']} {row['Home']} v {row['Away']}"
        matches.append(
            Match(
                div=div,
                season=_goals_only_season(row["Season"]),
                date=_parse_date(row["Date"], where),
                home=row["Home"].strip(),
                away=row["Away"].strip(),
                home_goals=_int(row, "HG", where),
                away_goals=_int(row, "AG", where),
                home_xg=None,
                away_xg=None,
                home_shots=None,
                away_shots=None,
                home_sot=None,
                away_sot=None,
                home_corners=None,
                away_corners=None,
                home_yellow=None,
                away_yellow=None,
                home_red=None,
                away_red=None,
            )
        )
    return matches


def load_goals_only(country: str, div: str, cache_dir: Path) -> list[Match]:
    """Refresh a goals-only league; fall back to the cached copy, then to [] (league dropped)."""
    cache_file = cache_dir / "new" / f"{country}.csv"
    try:
        text = download(goals_only_url(country), cache_file, refresh=True)
    except IngestError as error:
        logger.warning("%s: source unreachable, using cached copy if present: %s", div, error)
        text = None
    else:
        if text is None:
            logger.warning("%s: source has no file (404), using cached copy if present", div)

    if text is None:
        text = _read_cache(cache_file)
    if text is None:
        logger.warning("%s: no usable data, league skipped", div)
        return []

    try:
        return parse_goals_only_csv(text, div)
    except IngestError as error:
        # Drop a bad copy so the next run downloads it again.
        logger.warning("%s: invalid CSV, league skipped: %s", div, error)
        cache_file.unlink(missing_ok=True)
        return []


def _read_cache(cache_file: Path) -> str | None:
    if not cache_file.exists():
        return None
    return _decode(cache_file.read_bytes())


def _goals_only_season(value: str) -> str:
    """'2026/2027' -> '2627' (football-data style); a plain year such as '2026' is kept."""
    start, slash, end = value.strip().partition("/")
    if slash:
        return start[-2:] + end[-2:]
    return start


def _decode(body: bytes) -> str:
    """Recent files are UTF-8 with a BOM; some older seasons are Windows-1252."""
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError:
        return body.decode("cp1252", errors="replace")


def download(url: str, cache_file: Path, refresh: bool) -> str | None:
    """Return the CSV text, from cache unless refresh is set. None when the server answers 404."""
    if cache_file.exists() and not refresh:
        return _decode(cache_file.read_bytes())

    body = _fetch(url)
    if body is None:
        return None

    text = _decode(body)

    # Cache only what was read successfully; a failed read must not leave a partial file.
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(body)
    return text


def load_matches(
    divs: list[str], seasons: list[str], cache_dir: Path, current_season: str
) -> list[Match]:
    matches = []
    for season in seasons:
        for div in divs:
            cache_file = cache_dir / season / f"{div}.csv"
            text = download(
                season_url(season, div), cache_file, refresh=season == current_season
            )
            if text is None:
                continue
            try:
                matches.extend(parse_season_csv(text, div, season))
            except IngestError:
                # Drop a bad cached copy so the next run downloads it again.
                cache_file.unlink(missing_ok=True)
                raise
    return matches


def _fetch(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last_error = error
        except OSError as error:
            last_error = error
        finally:
            # Be polite to the free site after every network call.
            time.sleep(PAUSE_SECONDS)
        if attempt < ATTEMPTS:
            time.sleep(BACKOFF_SECONDS)
    raise IngestError(f"download failed after {ATTEMPTS} attempts: {url}: {last_error}")


def _strip_bom(text: str) -> str:
    return text.lstrip("﻿")


def _require_columns(fieldnames: list[str] | None, required: tuple[str, ...], where: str) -> None:
    if fieldnames is None:
        raise IngestError(f"{where}: empty CSV")
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise IngestError(f"{where}: missing columns {', '.join(missing)}")


def _parse_date(value: str, where: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise IngestError(f"{where}: unparseable date {value!r}")


_COUNT_COLUMNS = {
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_sot",
    "AST": "away_sot",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow",
    "AY": "away_yellow",
    "HR": "home_red",
    "AR": "away_red",
}


def _count_stats(row: dict[str, str], where: str) -> dict[str, int] | None:
    # A played row with a blank or non-integer count is skipped, so one half-filled row
    # never fails the whole load. Returns None when the row must be skipped.
    counts = {}
    for column, field in _COUNT_COLUMNS.items():
        value = row[column].strip()
        try:
            counts[field] = int(value)
        except ValueError:
            logger.warning("skipping %s: %s is not an integer (%r)", where, column, value)
            return None
    return counts


def _int(row: dict[str, str], column: str, where: str) -> int:
    value = row[column].strip()
    try:
        return int(value)
    except ValueError as error:
        raise IngestError(f"{where}: {column} is not an integer: {value!r}") from error


def _optional_float(row: dict[str, str], column: str, where: str) -> float | None:
    # Older seasons have no xG: the column may be missing or blank. That is null, never 0.
    value = (row.get(column) or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as error:
        raise IngestError(f"{where}: {column} is not a number: {value!r}") from error
