import {
  goalLambdas,
  goalMarkets,
  probOver,
  scoreMatrix,
  teamGoalsOver,
} from "./probability";
import type { LeagueData, StatModel, StatName, UefaData, UefaOffset } from "./types";

export type MarketStat = "goals" | StatName;

export interface Market {
  id: string;
  label: string;
  scope: "match" | "home" | "away";
  line: number | null;
  /** Mean used by the model; null for 1X2 and BTTS. */
  expected: number | null;
  probability: number;
}

/** One team's side of a cross-league UEFA match: its name, league code and that league's data. */
export interface CrossLeagueSide {
  name: string;
  code: string;
  league: LeagueData;
}

export const MATCH_LINES: Record<MarketStat, number> = {
  goals: 2.5,
  corners: 9.5,
  cards: 4.5,
  shots: 24.5,
  shots_on_target: 8.5,
};

export const TEAM_LINES: Record<MarketStat, number> = {
  goals: 1.5,
  corners: 4.5,
  cards: 1.5,
  shots: 12.5,
  shots_on_target: 4.5,
};

const STAT_LABELS: Record<MarketStat, string> = {
  goals: "goles",
  corners: "córners",
  cards: "tarjetas",
  shots: "tiros",
  shots_on_target: "tiros al arco",
};

const STAT_NAMES: StatName[] = ["corners", "cards", "shots", "shots_on_target"];

export class TeamNotFoundError extends Error {
  readonly team: string;

  constructor(team: string) {
    super(`Team not found: ${team}`);
    this.name = "TeamNotFoundError";
    this.team = team;
  }
}

function requireTeam(teams: Record<string, unknown>, team: string): void {
  if (!Object.hasOwn(teams, team)) throw new TeamNotFoundError(team);
}

/** "Más de 2.5 goles". Team rows share this label; the tab already names the team. */
function overLabel(line: number, stat: string): string {
  return `Más de ${line} ${stat}`;
}

/** Expected count for the home and away side of a stat, from the multiplicative model. */
function statMeans(model: StatModel, home: string, away: string): { home: number; away: number } {
  requireTeam(model.teams, home);
  requireTeam(model.teams, away);
  const homeRatios = model.teams[home];
  const awayRatios = model.teams[away];
  return {
    home: model.avg_home * homeRatios.home_for * awayRatios.away_against,
    away: model.avg_away * awayRatios.away_for * homeRatios.home_against,
  };
}

/** P(home + away goals > line) from a truncated score matrix. */
function matchGoalsOver(matrix: number[][], line: number): number {
  let total = 0;
  matrix.forEach((row, i) => {
    row.forEach((cell, j) => {
      if (i + j > line) total += cell;
    });
  });
  return total;
}

/** Goal rates of one fixture and the low-score correction, the same input for both models. */
interface GoalInput {
  home: number;
  away: number;
  rho: number;
}

/** Expected means and dispersions of one stat, the same input for both models. */
interface StatInput {
  stat: StatName;
  home: number;
  away: number;
  dispersionTotal: number | null;
  dispersionTeam: number | null;
}

/** Every market from a goal model and the stats that are available. */
function buildMarkets(goal: GoalInput, stats: StatInput[]): Market[] {
  const matrix = scoreMatrix(goal.home, goal.away, goal.rho);
  const outcomes = goalMarkets(matrix);

  const markets: Market[] = [
    { id: "1", label: "Gana local", scope: "match", line: null, expected: null, probability: outcomes.home },
    { id: "X", label: "Empate", scope: "match", line: null, expected: null, probability: outcomes.draw },
    { id: "2", label: "Gana visita", scope: "match", line: null, expected: null, probability: outcomes.away },
    { id: "btts", label: "Ambos marcan", scope: "match", line: null, expected: null, probability: outcomes.btts },
    {
      id: "goals_over",
      label: overLabel(MATCH_LINES.goals, STAT_LABELS.goals),
      scope: "match",
      line: MATCH_LINES.goals,
      expected: goal.home + goal.away,
      probability: matchGoalsOver(matrix, MATCH_LINES.goals),
    },
    {
      id: "goals_home_over",
      label: overLabel(TEAM_LINES.goals, STAT_LABELS.goals),
      scope: "home",
      line: TEAM_LINES.goals,
      expected: goal.home,
      probability: teamGoalsOver(matrix, "home", TEAM_LINES.goals),
    },
    {
      id: "goals_away_over",
      label: overLabel(TEAM_LINES.goals, STAT_LABELS.goals),
      scope: "away",
      line: TEAM_LINES.goals,
      expected: goal.away,
      probability: teamGoalsOver(matrix, "away", TEAM_LINES.goals),
    },
  ];

  for (const input of stats) {
    const { stat } = input;
    const total = input.home + input.away;
    const matchLine = MATCH_LINES[stat];
    const teamLine = TEAM_LINES[stat];

    markets.push(
      {
        id: `${stat}_over`,
        label: overLabel(matchLine, STAT_LABELS[stat]),
        scope: "match",
        line: matchLine,
        expected: total,
        probability: probOver(matchLine, total, input.dispersionTotal),
      },
      {
        id: `${stat}_home_over`,
        label: overLabel(teamLine, STAT_LABELS[stat]),
        scope: "home",
        line: teamLine,
        expected: input.home,
        probability: probOver(teamLine, input.home, input.dispersionTeam),
      },
      {
        id: `${stat}_away_over`,
        label: overLabel(teamLine, STAT_LABELS[stat]),
        scope: "away",
        line: teamLine,
        expected: input.away,
        probability: probOver(teamLine, input.away, input.dispersionTeam),
      },
    );
  }

  return markets;
}

/**
 * Every market for one fixture. Throws TeamNotFoundError when a team is not
 * in the league's data.
 */
export function matchMarkets(league: LeagueData, home: string, away: string): Market[] {
  requireTeam(league.goals.teams, home);
  requireTeam(league.goals.teams, away);

  const lambdas = goalLambdas(league.goals, home, away);
  const stats: StatInput[] = [];
  for (const stat of STAT_NAMES) {
    // Goals-only leagues have no stats; their stat markets are hidden, never computed as NaN.
    const model = league.stats?.[stat];
    if (!model) continue;
    const means = statMeans(model, home, away);
    stats.push({
      stat,
      home: means.home,
      away: means.away,
      dispersionTotal: model.dispersion_total,
      dispersionTeam: model.dispersion_team,
    });
  }

  return buildMarkets({ home: lambdas.home, away: lambdas.away, rho: league.goals.rho }, stats);
}

/**
 * True when the UEFA cross-league model can price this pair: the model is calibrated and both
 * leagues have offsets. Otherwise the match shows its data without probabilities.
 */
export function crossLeagueAvailable(uefa: UefaData | null, homeCode: string, awayCode: string): boolean {
  if (!uefa || !uefa.calibrated) return false;
  return Object.hasOwn(uefa.offsets, homeCode) && Object.hasOwn(uefa.offsets, awayCode);
}

function offsetOf(uefa: UefaData, code: string): UefaOffset {
  const offset = uefa.offsets[code];
  if (!offset) throw new Error(`No UEFA offsets for league ${code}`);
  return offset;
}

/** Stat means from two leagues: the geometric mean of their averages, so neither league dominates. */
function geometricMean(home: number, away: number): number {
  return Math.sqrt(home * away);
}

/** Mean of two leagues' dispersions; Poisson (null) when either league has none. */
function pooledDispersion(home: number | null, away: number | null): number | null {
  return home === null || away === null ? null : (home + away) / 2;
}

/**
 * Every market for a UEFA match between teams of two leagues. Goals use the cross-league model
 * from uefa.json; stats use each team's own league, and are left out when either league has none.
 * Throws TeamNotFoundError when a team is not in its league's data. Check crossLeagueAvailable first.
 */
export function crossLeagueMarkets(home: CrossLeagueSide, away: CrossLeagueSide, uefa: UefaData): Market[] {
  requireTeam(home.league.goals.teams, home.name);
  requireTeam(away.league.goals.teams, away.name);
  const homeOffset = offsetOf(uefa, home.code);
  const awayOffset = offsetOf(uefa, away.code);
  const homeRatings = home.league.goals.teams[home.name];
  const awayRatings = away.league.goals.teams[away.name];

  const goal: GoalInput = {
    home: Math.exp(
      homeRatings.attack + homeOffset.attack + awayRatings.defense + awayOffset.defense + uefa.home_advantage,
    ),
    away: Math.exp(awayRatings.attack + awayOffset.attack + homeRatings.defense + homeOffset.defense),
    rho: (home.league.goals.rho + away.league.goals.rho) / 2,
  };

  const stats: StatInput[] = [];
  for (const stat of STAT_NAMES) {
    const homeModel = home.league.stats?.[stat];
    const awayModel = away.league.stats?.[stat];
    if (!homeModel || !awayModel) continue;
    requireTeam(homeModel.teams, home.name);
    requireTeam(awayModel.teams, away.name);
    const homeStat = homeModel.teams[home.name];
    const awayStat = awayModel.teams[away.name];
    stats.push({
      stat,
      home: geometricMean(homeModel.avg_home, awayModel.avg_home) * homeStat.home_for * awayStat.away_against,
      away: geometricMean(homeModel.avg_away, awayModel.avg_away) * awayStat.away_for * homeStat.home_against,
      dispersionTotal: pooledDispersion(homeModel.dispersion_total, awayModel.dispersion_total),
      dispersionTeam: pooledDispersion(homeModel.dispersion_team, awayModel.dispersion_team),
    });
  }

  return buildMarkets(goal, stats);
}
