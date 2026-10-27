from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Match:
    div: str
    season: str
    date: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    home_xg: float | None
    away_xg: float | None
    home_shots: int
    away_shots: int
    home_sot: int
    away_sot: int
    home_corners: int
    away_corners: int
    home_yellow: int
    away_yellow: int
    home_red: int
    away_red: int

    @property
    def home_cards(self) -> int:
        """Card points for the home side: yellow = 1, red = 2 (Betano settlement)."""
        return self.home_yellow + 2 * self.home_red

    @property
    def away_cards(self) -> int:
        """Card points for the away side: yellow = 1, red = 2 (Betano settlement)."""
        return self.away_yellow + 2 * self.away_red


@dataclass(frozen=True)
class Fixture:
    div: str
    date: date
    time: str
    home: str
    away: str
