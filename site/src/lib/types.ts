// Mirrors contract/data-contract.md. Field names match the JSON exactly.
// Nullable fields are typed `number | null`; everything else is a plain number or string.

export type StatName = "corners" | "cards" | "shots" | "shots_on_target";

export interface IndexLeague {
  code: string;
  name: string;
  teams: string[];
}

export interface TodayMatch {
  league: string;
  date: string;
  time: string;
  home: string;
  away: string;
}

/** index.json */
export interface IndexData {
  generated_at: string;
  season: string;
  leagues: IndexLeague[];
  today: TodayMatch[];
}

export interface TeamGoalRatings {
  attack: number;
  defense: number;
}

/** leagues/<code>.json → goals */
export interface GoalsModel {
  home_advantage: number;
  rho: number;
  teams: Record<string, TeamGoalRatings>;
}

export interface StatTeamRatios {
  home_for: number;
  home_against: number;
  away_for: number;
  away_against: number;
}

/** leagues/<code>.json → stats.<name> */
export interface StatModel {
  avg_home: number;
  avg_away: number;
  dispersion_team: number | null;
  dispersion_total: number | null;
  teams: Record<string, StatTeamRatios>;
}

/** One side (all, home or away) of a team's season. Per-match averages unless noted. */
/** Per-match averages and fractions are null when `matches` is 0 (e.g. no away games yet). */
export interface SeasonSide {
  matches: number;
  position: number;
  points: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number | null;
  goals_against: number | null;
  xg_for: number | null;
  xg_against: number | null;
  shots_for: number | null;
  shots_against: number | null;
  shots_on_target_for: number | null;
  shots_on_target_against: number | null;
  corners_for: number | null;
  corners_against: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
  /** 0–1 fraction */
  btts_pct: number | null;
  /** 0–1 fraction */
  over_2_5_pct: number | null;
  clean_sheets: number;
}

export interface TeamSeason {
  all: SeasonSide;
  home: SeasonSide;
  away: SeasonSide;
}

/** One of a team's most recent matches. Cards are card points (yellow = 1, red = 2). */
export interface LastMatch {
  date: string;
  league: string;
  /** "H" or "A" */
  venue: string;
  opponent: string;
  goals_for: number;
  goals_against: number;
  /** "W", "D" or "L" */
  result: string;
  xg_for: number | null;
  xg_against: number | null;
  shots_for: number;
  shots_against: number;
  shots_on_target_for: number;
  shots_on_target_against: number;
  corners_for: number;
  corners_against: number;
  cards_for: number;
  cards_against: number;
}

export interface TeamData {
  season: TeamSeason;
  last6: LastMatch[];
}

/** leagues/<code>.json */
export interface LeagueData {
  league: string;
  season: string;
  goals: GoalsModel;
  stats: Record<StatName, StatModel>;
  teams: Record<string, TeamData>;
}

/** One past meeting between two teams. */
export interface Meeting {
  date: string;
  league: string;
  home: string;
  away: string;
  home_goals: number;
  away_goals: number;
  home_shots: number;
  away_shots: number;
  home_shots_on_target: number;
  away_shots_on_target: number;
  home_corners: number;
  away_corners: number;
  home_cards: number;
  away_cards: number;
}

/** h2h/<code>.json. Keys are "TeamA|TeamB" with names sorted alphabetically. */
export interface H2HData {
  league: string;
  pairs: Record<string, Meeting[]>;
}
