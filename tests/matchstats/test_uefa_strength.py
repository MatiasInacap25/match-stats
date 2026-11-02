import math
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from matchstats.goals_model import fit_goals_model
from matchstats.match import Match
from matchstats.uefa_strength import (
    UefaResult,
    backtest,
    domestic_fits,
    fit_league_offsets,
    parse_uefa_results,
    uefa_result_urls,
)

FIXTURES = Path(__file__).parent / "fixtures"
YEAR = 2025
ZERO = {"attack": 0.0, "defense": 0.0}


def club(code: str, i: int) -> str:
    """Letter-only names: team resolution drops digits, so "Club 01" and "Club 02" would collide."""
    return f"{code} Club {chr(97 + i // 26)}{chr(97 + i % 26)}"


def domestic_world(teams_by_league: dict[str, int], year: int, rng) -> dict:
    """Domestic goals objects for each league: random team strengths, no league offsets."""
    domestic = {}
    for code, count in teams_by_league.items():
        teams = {
            club(code, i): {
                "attack": round(float(rng.normal(0, 0.2)), 4),
                "defense": round(float(rng.normal(0, 0.2)), 4),
            }
            for i in range(count)
        }
        domestic[(code, year)] = {"home_advantage": 0.25, "rho": 0.0, "teams": teams}
    return domestic


def simulate(domestic: dict, year: int, offsets: dict, pairs: list[tuple[str, str]], rng) -> list[UefaResult]:
    """Poisson results of one UEFA match per (home league, away league) pair, with the cross-league model."""
    results = []
    for home_code, away_code in pairs:
        home_teams = domestic[(home_code, year)]["teams"]
        away_teams = domestic[(away_code, year)]["teams"]
        home = str(rng.choice(list(home_teams)))
        away = str(rng.choice(list(away_teams)))
        hp, ap = home_teams[home], away_teams[away]
        lam = math.exp(
            hp["attack"] + offsets[home_code]["attack"] + ap["defense"] + offsets[away_code]["defense"] + 0.2
        )
        mu = math.exp(ap["attack"] + offsets[away_code]["attack"] + hp["defense"] + offsets[home_code]["defense"])
        results.append(
            UefaResult(
                year=year,
                kickoff_utc=datetime(year, 9, 1, tzinfo=UTC),
                home=home,
                away=away,
                home_goals=int(rng.poisson(lam)),
                away_goals=int(rng.poisson(mu)),
                home_league=home_code,
                away_league=away_code,
            )
        )
    return results


def test_uefa_result_urls_use_fixturedownload_slugs():
    assert uefa_result_urls([2025]) == {
        "UCL-2025": "https://fixturedownload.com/feed/json/champions-league-2025",
        "UEL-2025": "https://fixturedownload.com/feed/json/europa-league-2025",
        "UECL-2025": "https://fixturedownload.com/feed/json/conference-league-2025",
    }


def test_parse_uefa_results_skips_unplayed_rows_and_applies_league_lookup():
    text = (FIXTURES / "uefa_cl_sample.json").read_text(encoding="utf-8")

    results = parse_uefa_results(text, YEAR, team_league=lambda name: "N1" if name == "PSV" else None)

    assert len(results) == 6
    first = results[0]
    assert first == UefaResult(
        year=YEAR,
        kickoff_utc=datetime(2025, 9, 16, 16, 45, tzinfo=UTC),
        home="PSV",
        away="Union SG",
        home_goals=1,
        away_goals=3,
        home_league="N1",
        away_league=None,
    )


def test_offsets_recover_synthetic_strength():
    rng = np.random.default_rng(1)
    domestic = domestic_world({"E0": 18, "T1": 18}, YEAR, rng)
    truth = {"E0": ZERO, "T1": {"attack": math.log(0.7), "defense": 0.0}}
    results = simulate(domestic, YEAR, truth, [("E0", "T1"), ("T1", "E0")] * 400, rng)

    fitted = fit_league_offsets(results, domestic)

    assert fitted["offsets"]["E0"] == {"attack": 0.0, "defense": 0.0}
    t1_attack = fitted["offsets"]["T1"]["attack"]
    assert t1_attack < 0
    assert abs(t1_attack - math.log(0.7)) < 0.1


def test_l2_keeps_sparse_league_near_zero():
    rng = np.random.default_rng(2)
    domestic = domestic_world({"E0": 18, "T1": 18, "N1": 18}, YEAR, rng)
    truth = {"E0": ZERO, "T1": {"attack": -0.3, "defense": 0.1}, "N1": {"attack": 0.5, "defense": -0.4}}
    results = simulate(domestic, YEAR, truth, [("E0", "T1"), ("T1", "E0")] * 300 + [("N1", "E0"), ("E0", "N1")], rng)

    offsets = fit_league_offsets(results, domestic)["offsets"]["N1"]

    assert abs(offsets["attack"]) < 0.05
    assert abs(offsets["defense"]) < 0.05


def test_same_league_uefa_matches_ignored_or_neutral():
    rng = np.random.default_rng(4)
    domestic = domestic_world({"E0": 18, "T1": 18}, YEAR, rng)
    truth = {"E0": ZERO, "T1": {"attack": -0.3, "defense": 0.0}}
    cross = simulate(domestic, YEAR, truth, [("E0", "T1"), ("T1", "E0")] * 100, rng)
    same = simulate(domestic, YEAR, truth, [("E0", "E0"), ("T1", "T1")] * 100, rng)

    assert fit_league_offsets(cross + same, domestic) == fit_league_offsets(cross, domestic)


def test_backtest_reports_three_log_losses():
    rng = np.random.default_rng(6)
    domestic = domestic_world({"E0": 18, "T1": 18}, 2024, rng) | domestic_world({"E0": 18, "T1": 18}, 2025, rng)
    truth = {"E0": ZERO, "T1": {"attack": -0.3, "defense": 0.0}}
    results = simulate(domestic, 2024, truth, [("E0", "T1"), ("T1", "E0")] * 150, rng)
    results += simulate(domestic, 2025, truth, [("E0", "T1"), ("T1", "E0")] * 60, rng)

    result = backtest(results, domestic)

    assert set(result) == {"held_out", "matches", "log_loss", "log_loss_unadjusted", "log_loss_baseline"}
    assert result["held_out"] == 2025
    assert result["matches"] == 120


def test_domestic_fits_use_only_matches_in_the_three_seasons_before_season_start():
    rng = np.random.default_rng(8)
    names = [club("E0", i) for i in range(6)]
    matches = []
    for when in (date(2021, 9, 1), date(2022, 9, 1), date(2025, 1, 10), date(2025, 6, 30), date(2025, 9, 1)):
        home, away = rng.choice(names, size=2, replace=False)
        matches.append(_domestic_match(when, str(home), str(away), int(rng.poisson(1.5)), int(rng.poisson(1.1))))

    fits = domestic_fits({"E0": matches}, [2025])

    window = [m for m in matches if date(2022, 7, 1) <= m.date < date(2025, 7, 1)]
    assert fits[("E0", 2025)] == fit_goals_model(window, ref_date=date(2025, 7, 1))


def _domestic_match(when: date, home: str, away: str, home_goals: int, away_goals: int) -> Match:
    return Match(
        div="E0",
        season="2425",
        date=when,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
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
