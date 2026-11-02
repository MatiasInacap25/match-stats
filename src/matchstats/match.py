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
    # Stat fields are None for goals-only leagues, which publish results but no match stats.
    home_shots: int | None
    away_shots: int | None
    home_sot: int | None
    away_sot: int | None
    home_corners: int | None
    away_corners: int | None
    home_yellow: int | None
    away_yellow: int | None
    home_red: int | None
    away_red: int | None

    @property
    def home_cards(self) -> int | None:
        """Card points for the home side: yellow = 1, red = 2 (Betano settlement). None when unknown."""
        if self.home_yellow is None or self.home_red is None:
            return None
        return self.home_yellow + 2 * self.home_red

    @property
    def away_cards(self) -> int | None:
        """Card points for the away side: yellow = 1, red = 2 (Betano settlement). None when unknown."""
        if self.away_yellow is None or self.away_red is None:
            return None
        return self.away_yellow + 2 * self.away_red


@dataclass(frozen=True)
class Fixture:
    div: str
    date: date
    time: str
    home: str
    away: str
