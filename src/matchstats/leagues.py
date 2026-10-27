from datetime import date

TOP_LEAGUES: dict[str, str] = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
}

SECOND_DIVISION: dict[str, str] = {
    "E0": "E1",
    "SP1": "SP2",
    "I1": "I2",
    "D1": "D2",
    "F1": "F2",
}


def season_code(d: date) -> str:
    """Season code for a date. Seasons start on July 1: 2026-07-01 is '2627'."""
    start_year = d.year if d.month >= 7 else d.year - 1
    return _code(start_year)


def season_label(code: str) -> str:
    """'2627' -> '2026/27'."""
    return f"20{code[:2]}/{code[2:]}"


def recent_seasons(current: str, n: int) -> list[str]:
    """The current season and the n-1 before it, newest first."""
    start_year = 2000 + int(current[:2])
    return [_code(start_year - i) for i in range(n)]


def _code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"
