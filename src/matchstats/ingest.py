import csv
import io
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from matchstats.match import Fixture, Match

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
_SEASON_BASE_URL = "https://www.football-data.co.uk/mmz4281"
USER_AGENT = "matchstats/0.1"
TIMEOUT_SECONDS = 30
ATTEMPTS = 3
BACKOFF_SECONDS = 2
PAUSE_SECONDS = 1

_SEASON_COLUMNS = (
    "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG",
    "HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR",
)
_FIXTURE_COLUMNS = ("Div", "Date", "Time", "HomeTeam", "AwayTeam")


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
                home_shots=_int(row, "HS", where),
                away_shots=_int(row, "AS", where),
                home_sot=_int(row, "HST", where),
                away_sot=_int(row, "AST", where),
                home_corners=_int(row, "HC", where),
                away_corners=_int(row, "AC", where),
                home_yellow=_int(row, "HY", where),
                away_yellow=_int(row, "AY", where),
                home_red=_int(row, "HR", where),
                away_red=_int(row, "AR", where),
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


def download(url: str, cache_file: Path, refresh: bool) -> str | None:
    """Return the CSV text, from cache unless refresh is set. None when the server answers 404."""
    if cache_file.exists() and not refresh:
        return cache_file.read_bytes().decode("utf-8-sig")

    body = _fetch(url)
    if body is None:
        return None

    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise IngestError(f"not UTF-8 text: {url}: {error}") from error

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
