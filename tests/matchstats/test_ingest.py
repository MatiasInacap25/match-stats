import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from matchstats import ingest
from matchstats.ingest import (
    FIXTURES_URL,
    IngestError,
    download,
    load_matches,
    parse_fixtures_csv,
    parse_season_csv,
    season_url,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEASON_CSV = (FIXTURES_DIR / "E0_2627_sample.csv").read_text(encoding="utf-8-sig")
FIXTURES_CSV = (FIXTURES_DIR / "fixtures_sample.csv").read_text(encoding="utf-8-sig")


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)


def test_season_url_and_fixtures_url():
    assert season_url("2627", "E0") == "https://www.football-data.co.uk/mmz4281/2627/E0.csv"
    assert FIXTURES_URL == "https://www.football-data.co.uk/fixtures.csv"


def test_parse_season_csv_real_sample():
    matches = parse_season_csv(SEASON_CSV, "E0", "2627")

    # 5 real rows + the no-xG row; the postponed row (empty FTHG) is skipped.
    assert len(matches) == 6
    first = matches[0]
    assert first.div == "E0"
    assert first.season == "2627"
    assert first.date == date(2026, 8, 21)
    assert isinstance(first.date, date)
    assert first.home == "Arsenal"
    assert first.away == "Coventry"
    assert first.home_goals == 3
    assert first.away_goals == 0
    assert first.home_shots == 20
    assert first.home_sot == 6
    assert first.home_corners == 8
    assert first.home_yellow == 1
    assert first.home_red == 0
    assert first.home_xg == pytest.approx(1.88)


def test_cards_are_points():
    text = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HxG,AxG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR\n"
        "E0,21/08/2026,20:00,Arsenal,Coventry,1,0,,,10,5,4,2,6,3,2,0,1,0\n"
    )
    (match,) = parse_season_csv(text, "E0", "2627")

    assert match.home_cards == 4
    assert match.away_cards == 0


def test_missing_xg_is_none():
    matches = parse_season_csv(SEASON_CSV, "E0", "2627")
    no_xg = next(m for m in matches if m.home == "Brentford")

    assert no_xg.home_xg is None
    assert no_xg.away_xg is None


def test_missing_xg_column_is_none():
    text = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR\n"
        "E0,06/08/10,20:00,Arsenal,Coventry,1,0,10,5,4,2,6,3,2,0,0,0\n"
    )
    (match,) = parse_season_csv(text, "E0", "1011")

    assert match.home_xg is None
    assert match.date == date(2010, 8, 6)


def test_skips_rows_without_result():
    matches = parse_season_csv(SEASON_CSV, "E0", "2627")

    assert all(m.home_goals is not None for m in matches)
    assert not any(m.home == "Brighton" and m.away == "Aston Villa" for m in matches)


def test_two_digit_year():
    text = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR\n"
        "E0,25/10/26,15:00,Arsenal,Coventry,1,0,10,5,4,2,6,3,2,0,0,0\n"
    )
    (match,) = parse_season_csv(text, "E0", "2627")

    assert match.date == date(2026, 10, 25)


def test_parse_fixtures():
    fixtures = parse_fixtures_csv(FIXTURES_CSV)

    assert len(fixtures) == 5
    first = fixtures[0]
    assert first.div == "E0"
    assert first.date == date(2026, 10, 23)
    assert first.time == "20:00"
    assert first.home == "Ipswich"
    assert first.away == "Nott'm Forest"


def test_download_uses_cache_unless_refresh(monkeypatch, tmp_path):
    cache_file = tmp_path / "2627" / "E0.csv"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("cached", encoding="utf-8")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(b"fresh")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert download("https://example.test/E0.csv", cache_file, refresh=False) == "cached"
    assert calls == []

    assert download("https://example.test/E0.csv", cache_file, refresh=True) == "fresh"
    assert len(calls) == 1
    assert calls[0][0].get_header("User-agent") == "matchstats/0.1"
    assert cache_file.read_bytes() == b"fresh"


def test_download_404_returns_none(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    cache_file = tmp_path / "1011" / "E0.csv"

    assert download("https://example.test/missing.csv", cache_file, refresh=False) is None
    assert not cache_file.exists()


def test_download_retries_then_raises(monkeypatch, tmp_path):
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(request)
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    cache_file = tmp_path / "2627" / "E0.csv"

    with pytest.raises(IngestError):
        download("https://example.test/E0.csv", cache_file, refresh=False)

    assert len(attempts) == 3
    assert not cache_file.exists()


def test_load_matches_skips_missing_season(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        if "/2526/" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)
        return FakeResponse(SEASON_CSV.encode("utf-8-sig"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    matches = load_matches(["E0"], ["2627", "2526"], tmp_path, current_season="2627")

    assert len(matches) == 6
    assert {m.season for m in matches} == {"2627"}
    assert (tmp_path / "2627" / "E0.csv").exists()
    assert not (tmp_path / "2526" / "E0.csv").exists()


def test_load_matches_uses_cache_for_past_seasons(monkeypatch, tmp_path):
    past = tmp_path / "2526" / "E0.csv"
    past.parent.mkdir(parents=True)
    past.write_bytes(SEASON_CSV.encode("utf-8-sig"))
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse(SEASON_CSV.encode("utf-8-sig"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    load_matches(["E0"], ["2526", "2627"], tmp_path, current_season="2627")

    assert calls == ["https://www.football-data.co.uk/mmz4281/2627/E0.csv"]
