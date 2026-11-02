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

/**
 * One fixture in index.json → upcoming. `kickoff_utc` is an ISO 8601 UTC instant.
 * `competition` is a league code, "UCL" (Champions League), "UEL" (Europa League),
 * "UECL" (Conference League), or "DFB" for DFB-Pokal.
 * `league` is the top-5 league whose data has both teams, or null when none does.
 * `home_league` / `away_league` are the league code whose current teams uniquely contain that
 * team, or null when none or more than one does. Missing on files written before they existed.
 */
export interface UpcomingMatch {
  competition: string;
  competition_name: string;
  kickoff_utc: string;
  home: string;
  away: string;
  league: string | null;
  home_league?: string | null;
  away_league?: string | null;
}

/** index.json */
export interface IndexData {
  generated_at: string;
  season: string;
  leagues: IndexLeague[];
  today: TodayMatch[];
  /** Optional until the nightly job publishes it. */
  upcoming?: UpcomingMatch[];
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

/**
 * One side (all, home or away) of a team's season. Per-match averages unless noted.
 * Averages and fractions are null when `matches` is 0 (e.g. no away games yet).
 */
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

/**
 * One of a team's most recent matches. Cards are card points (yellow = 1, red = 2).
 * Stat fields are null for goals-only leagues (NOR, AUT).
 */
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
  shots_for: number | null;
  shots_against: number | null;
  shots_on_target_for: number | null;
  shots_on_target_against: number | null;
  corners_for: number | null;
  corners_against: number | null;
  cards_for: number | null;
  cards_against: number | null;
}

export interface TeamData {
  season: TeamSeason;
  last6: LastMatch[];
}

/**
 * leagues/<code>.json. Goals-only leagues (NOR, AUT) have no `stats` key, and their season-side
 * stat fields and `last6` stat fields are null. Check `stats` before reading it.
 */
export interface LeagueData {
  league: string;
  season: string;
  goals: GoalsModel;
  stats?: Record<StatName, StatModel>;
  teams: Record<string, TeamData>;
}

/** One league's cross-league offsets, as used by the UEFA goals model. */
export interface UefaOffset {
  attack: number;
  defense: number;
}

/**
 * uefa.json. `calibrated: false` means the cross-league model is not usable; UEFA matches then
 * show data without probabilities. A league missing from `offsets` has no probabilities either.
 */
export interface UefaData {
  calibrated: boolean;
  home_advantage: number;
  offsets: Record<string, UefaOffset>;
  seasons: number[];
  backtest: {
    held_out: number;
    matches: number;
    log_loss: number;
    log_loss_unadjusted: number;
    log_loss_baseline: number;
  };
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
