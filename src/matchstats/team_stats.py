from dataclasses import dataclass
from datetime import date

from matchstats.match import Match


@dataclass
class _Tally:
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0

    def add(self, goals_for: int, goals_against: int) -> None:
        self.goals_for += goals_for
        self.goals_against += goals_against
        if goals_for > goals_against:
            self.points += 3
        elif goals_for == goals_against:
            self.points += 1


def league_table(matches: list[Match]) -> dict[str, tuple[int, int]]:
    """Team -> (position, points). Ties: goal difference, goals for, then name."""
    tallies: dict[str, _Tally] = {}
    for m in matches:
        tallies.setdefault(m.home, _Tally()).add(m.home_goals, m.away_goals)
        tallies.setdefault(m.away, _Tally()).add(m.away_goals, m.home_goals)

    ordered = sorted(
        tallies.items(),
        key=lambda item: (
            -item[1].points,
            -(item[1].goals_for - item[1].goals_against),
            -item[1].goals_for,
            item[0],
        ),
    )
    return {team: (pos, t.points) for pos, (team, t) in enumerate(ordered, start=1)}


@dataclass(frozen=True)
class _Row:
    """One team's view of one match."""

    date: date
    league: str
    venue: str
    opponent: str
    goals_for: int
    goals_against: int
    xg_for: float | None
    xg_against: float | None
    shots_for: int | None
    shots_against: int | None
    shots_on_target_for: int | None
    shots_on_target_against: int | None
    corners_for: int | None
    corners_against: int | None
    yellow_for: int | None
    red_for: int | None
    yellow_against: int | None
    red_against: int | None

    @property
    def result(self) -> str:
        if self.goals_for > self.goals_against:
            return "W"
        if self.goals_for == self.goals_against:
            return "D"
        return "L"

    @property
    def cards_for(self) -> int | None:
        if self.yellow_for is None or self.red_for is None:
            return None
        return self.yellow_for + 2 * self.red_for

    @property
    def cards_against(self) -> int | None:
        if self.yellow_against is None or self.red_against is None:
            return None
        return self.yellow_against + 2 * self.red_against


def _rows(matches: list[Match], team: str) -> list[_Row]:
    rows: list[_Row] = []
    for m in matches:
        if m.home == team:
            rows.append(
                _Row(
                    date=m.date,
                    league=m.div,
                    venue="H",
                    opponent=m.away,
                    goals_for=m.home_goals,
                    goals_against=m.away_goals,
                    xg_for=m.home_xg,
                    xg_against=m.away_xg,
                    shots_for=m.home_shots,
                    shots_against=m.away_shots,
                    shots_on_target_for=m.home_sot,
                    shots_on_target_against=m.away_sot,
                    corners_for=m.home_corners,
                    corners_against=m.away_corners,
                    yellow_for=m.home_yellow,
                    red_for=m.home_red,
                    yellow_against=m.away_yellow,
                    red_against=m.away_red,
                )
            )
        elif m.away == team:
            rows.append(
                _Row(
                    date=m.date,
                    league=m.div,
                    venue="A",
                    opponent=m.home,
                    goals_for=m.away_goals,
                    goals_against=m.home_goals,
                    xg_for=m.away_xg,
                    xg_against=m.home_xg,
                    shots_for=m.away_shots,
                    shots_against=m.home_shots,
                    shots_on_target_for=m.away_sot,
                    shots_on_target_against=m.home_sot,
                    corners_for=m.away_corners,
                    corners_against=m.home_corners,
                    yellow_for=m.away_yellow,
                    red_for=m.away_red,
                    yellow_against=m.home_yellow,
                    red_against=m.home_red,
                )
            )
    return rows


def season_stats(
    matches: list[Match], team: str, table: dict[str, tuple[int, int]]
) -> dict:
    """Contract `season` object: {"all", "home", "away"} for one team."""
    rows = _rows(matches, team)
    position, points = table.get(team, (None, None))
    return {
        "all": _side(rows, position, points),
        "home": _side([r for r in rows if r.venue == "H"], position, points),
        "away": _side([r for r in rows if r.venue == "A"], position, points),
    }


def _side(rows: list[_Row], position: int | None, points: int | None) -> dict:
    n = len(rows)

    def avg(values: list[float | None]) -> float | None:
        # Missing values (goals-only leagues) are skipped; None when nothing is known.
        known = [v for v in values if v is not None]
        return round(sum(known) / len(known), 2) if known else None

    def pct(flags: list[bool]) -> float | None:
        return round(sum(flags) / n, 3) if n else None

    return {
        "matches": n,
        "position": position,
        "points": points,
        "won": sum(1 for r in rows if r.result == "W"),
        "drawn": sum(1 for r in rows if r.result == "D"),
        "lost": sum(1 for r in rows if r.result == "L"),
        "goals_for": avg([r.goals_for for r in rows]),
        "goals_against": avg([r.goals_against for r in rows]),
        "xg_for": avg([r.xg_for for r in rows]),
        "xg_against": avg([r.xg_against for r in rows]),
        "shots_for": avg([r.shots_for for r in rows]),
        "shots_against": avg([r.shots_against for r in rows]),
        "shots_on_target_for": avg([r.shots_on_target_for for r in rows]),
        "shots_on_target_against": avg([r.shots_on_target_against for r in rows]),
        "corners_for": avg([r.corners_for for r in rows]),
        "corners_against": avg([r.corners_against for r in rows]),
        "yellow_cards": avg([r.yellow_for for r in rows]),
        "red_cards": avg([r.red_for for r in rows]),
        "btts_pct": pct([r.goals_for > 0 and r.goals_against > 0 for r in rows]),
        "over_2_5_pct": pct([r.goals_for + r.goals_against > 2 for r in rows]),
        "clean_sheets": sum(1 for r in rows if r.goals_against == 0),
    }


def last_matches(matches: list[Match], team: str, n: int = 6) -> list[dict]:
    """Contract `last6` items: the team's n most recent matches, newest first."""
    rows = sorted(_rows(matches, team), key=lambda r: r.date, reverse=True)[:n]
    return [
        {
            "date": r.date.isoformat(),
            "league": r.league,
            "venue": r.venue,
            "opponent": r.opponent,
            "goals_for": r.goals_for,
            "goals_against": r.goals_against,
            "result": r.result,
            "xg_for": r.xg_for,
            "xg_against": r.xg_against,
            "shots_for": r.shots_for,
            "shots_against": r.shots_against,
            "shots_on_target_for": r.shots_on_target_for,
            "shots_on_target_against": r.shots_on_target_against,
            "corners_for": r.corners_for,
            "corners_against": r.corners_against,
            "cards_for": r.cards_for,
            "cards_against": r.cards_against,
        }
        for r in rows
    ]


def pair_key(a: str, b: str) -> str:
    """Sorted team names joined by '|', e.g. 'Arsenal|Chelsea'."""
    return "|".join(sorted((a, b)))


def head_to_head(matches: list[Match], a: str, b: str) -> list[dict]:
    """Contract `meeting` items for a vs b at either venue, newest first."""
    pair = {a, b}
    meetings = sorted(
        (m for m in matches if {m.home, m.away} == pair),
        key=lambda m: m.date,
        reverse=True,
    )
    return [
        {
            "date": m.date.isoformat(),
            "league": m.div,
            "home": m.home,
            "away": m.away,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "home_shots": m.home_shots,
            "away_shots": m.away_shots,
            "home_shots_on_target": m.home_sot,
            "away_shots_on_target": m.away_sot,
            "home_corners": m.home_corners,
            "away_corners": m.away_corners,
            "home_cards": m.home_cards,
            "away_cards": m.away_cards,
        }
        for m in meetings
    ]
