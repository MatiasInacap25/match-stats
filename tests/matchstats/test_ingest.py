import logging
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
    goals_only_url,
    load_goals_only,
    load_matches,
    parse_fixtures_csv,
    parse_goals_only_csv,
    parse_season_csv,
    season_url,
)
from matchstats.match import Match
from matchstats.team_stats import league_table, season_stats

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEASON_CSV = (FIXTURES_DIR / "E0_2627_sample.csv").read_text(encoding="utf-8-sig")
FIXTURES_CSV = (FIXTURES_DIR / "fixtures_sample.csv").read_text(encoding="utf-8-sig")
NOR_CSV = (FIXTURES_DIR / "new_nor_sample.csv").read_text(encoding="utf-8-sig")
AUT_CSV = (FIXTURES_DIR / "new_aut_sample.csv").read_text(encoding="utf-8-sig")

GOALS_ONLY_STAT_FIELDS = (
    "home_xg", "away_xg", "home_shots", "away_shots", "home_sot", "away_sot",
    "home_corners", "away_corners", "home_yellow", "away_yellow", "home_red", "away_red",
)


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


def test_skips_played_row_with_blank_stats(caplog):
    text = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HxG,AxG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR\n"
        "E0,21/08/2026,20:00,Arsenal,Coventry,1,0,,,10,5,4,2,6,3,2,0,0,0\n"
        "E0,22/08/2026,15:00,Everton,Crystal Palace,2,1,,,8,6,3,2,,4,1,1,0,0\n"
        "E0,23/08/2026,15:00,Ipswich,Sunderland,0,0,,,7,7,2,2,5,5,2,2,0,0\n"
    )

    with caplog.at_level(logging.WARNING, logger="matchstats.ingest"):
        matches = parse_season_csv(text, "E0", "2627")

    assert [(m.home, m.away) for m in matches] == [
        ("Arsenal", "Coventry"),
        ("Ipswich", "Sunderland"),
    ]
    assert "E0 2627" in caplog.text
    assert "Everton" in caplog.text


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


def test_download_decodes_windows_1252_files(monkeypatch, tmp_path):
    # Seen live: football-data's I2 2018/19 file is not UTF-8 (byte 0xa0 = no-break space).
    body = "Div,HomeTeam\nI2,Virtus\xa0Entella\n".encode("cp1252")
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: FakeResponse(body))
    cache_file = tmp_path / "1819" / "I2.csv"

    assert download("https://example.test/I2.csv", cache_file, refresh=True) == "Div,HomeTeam\nI2,Virtus\xa0Entella\n"
    assert download("https://example.test/I2.csv", cache_file, refresh=False) == "Div,HomeTeam\nI2,Virtus\xa0Entella\n"


def test_goals_only_url():
    assert goals_only_url("NOR") == "https://www.football-data.co.uk/new/NOR.csv"


def test_parse_goals_only_csv_nor():
    matches = parse_goals_only_csv(NOR_CSV, "NOR")

    # The sample holds 2025 and 2026 rows; only the 2026 rows are season "2026".
    season_2026 = [m for m in matches if m.season == "2026"]
    assert len(season_2026) == 3
    kristiansund = next(m for m in season_2026 if m.home == "Kristiansund")
    assert kristiansund == Match(
        div="NOR",
        season="2026",
        date=date(2026, 3, 15),
        home="Kristiansund",
        away="Brann",
        home_goals=3,
        away_goals=2,
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


def test_parse_goals_only_csv_all_stats_are_none():
    matches = parse_goals_only_csv(NOR_CSV, "NOR")

    assert matches
    for match in matches:
        assert all(getattr(match, field) is None for field in GOALS_ONLY_STAT_FIELDS)
        assert match.home_cards is None
        assert match.away_cards is None


def test_parse_goals_only_csv_skips_rows_without_goals():
    text = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
        "Norway,Eliteserien,2026,14/03/2026,15:00,HamKam,Viking,2,1,H\n"
        "Norway,Eliteserien,2026,15/03/2026,13:30,Molde,Rosenborg,,,\n"
        "Norway,Eliteserien,2026,16/03/2026,13:30,Brann,Bodo/Glimt,1,,\n"
    )

    matches = parse_goals_only_csv(text, "NOR")

    assert [(m.home, m.away) for m in matches] == [("HamKam", "Viking")]
    assert matches[0].date == date(2026, 3, 14)


def test_goals_only_newest_season_in_file_renders_season_stats():
    matches = parse_goals_only_csv(NOR_CSV, "NOR")
    newest = max(m.season for m in matches)

    # Between seasons the file's newest season is already finished; it still gives season stats.
    assert newest == "2026"
    stats = season_stats(matches, "Brann", league_table(matches))
    assert stats["all"]["matches"] > 0
    assert stats["all"]["goals_for"] is not None
    assert stats["all"]["xg_for"] is None


def test_parse_goals_only_csv_aut_season_code():
    matches = parse_goals_only_csv(AUT_CSV, "AUT")

    assert {m.season for m in matches} == {"2526", "2627"}
    assert all(m.div == "AUT" for m in matches)


def test_parse_goals_only_csv_keeps_plain_year_season():
    text = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
        "Norway,Eliteserien,2025,29/03/2025,15:00,Stromsgodset,Rosenborg,1,2,A\n"
    )

    (match,) = parse_goals_only_csv(text, "NOR")

    assert match.season == "2025"


def test_load_goals_only_downloads_and_caches(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse(NOR_CSV.encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    matches = load_goals_only("NOR", "NOR", tmp_path)

    assert calls == ["https://www.football-data.co.uk/new/NOR.csv"]
    assert len(matches) == len(parse_goals_only_csv(NOR_CSV, "NOR"))
    assert (tmp_path / "new" / "NOR.csv").read_bytes() == NOR_CSV.encode("utf-8")


def test_load_goals_only_uses_cache_when_source_unreachable(monkeypatch, tmp_path):
    cached = tmp_path / "new" / "NOR.csv"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(NOR_CSV.encode("utf-8"))

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    matches = load_goals_only("NOR", "NOR", tmp_path)

    assert matches == parse_goals_only_csv(NOR_CSV, "NOR")
    assert cached.read_bytes() == NOR_CSV.encode("utf-8")


def test_load_goals_only_empty_when_unreachable_and_no_cache(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert load_goals_only("NOR", "NOR", tmp_path) == []


def test_load_goals_only_empty_on_404(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert load_goals_only("CZE", "CZE", tmp_path) == []
    assert not (tmp_path / "new" / "CZE.csv").exists()


def test_load_goals_only_drops_invalid_csv(monkeypatch, tmp_path):
    body = b"Country,League\nNorway,Eliteserien\n"
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: FakeResponse(body))

    assert load_goals_only("NOR", "NOR", tmp_path) == []
    assert not (tmp_path / "new" / "NOR.csv").exists()
