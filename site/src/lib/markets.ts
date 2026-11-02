import {
  goalLambdas,
  goalMarkets,
  probOver,
  scoreMatrix,
  teamGoalsOver,
} from "./probability";
import type { LeagueData, StatModel, StatName } from "./types";

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

/**
 * Every market for one fixture. Throws TeamNotFoundError when a team is not
 * in the league's data.
 */
export function matchMarkets(league: LeagueData, home: string, away: string): Market[] {
  requireTeam(league.goals.teams, home);
  requireTeam(league.goals.teams, away);

  const lambdas = goalLambdas(league.goals, home, away);
  const matrix = scoreMatrix(lambdas.home, lambdas.away, league.goals.rho);
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
      expected: lambdas.home + lambdas.away,
      probability: matchGoalsOver(matrix, MATCH_LINES.goals),
    },
    {
      id: "goals_home_over",
      label: overLabel(TEAM_LINES.goals, STAT_LABELS.goals),
      scope: "home",
      line: TEAM_LINES.goals,
      expected: lambdas.home,
      probability: teamGoalsOver(matrix, "home", TEAM_LINES.goals),
    },
    {
      id: "goals_away_over",
      label: overLabel(TEAM_LINES.goals, STAT_LABELS.goals),
      scope: "away",
      line: TEAM_LINES.goals,
      expected: lambdas.away,
      probability: teamGoalsOver(matrix, "away", TEAM_LINES.goals),
    },
  ];

  for (const stat of STAT_NAMES) {
    // Goals-only leagues have no stats; their stat markets are hidden, never computed as NaN.
    const model = league.stats?.[stat];
    if (!model) continue;
    const means = statMeans(model, home, away);
    const total = means.home + means.away;
    const matchLine = MATCH_LINES[stat];
    const teamLine = TEAM_LINES[stat];

    markets.push(
      {
        id: `${stat}_over`,
        label: overLabel(matchLine, STAT_LABELS[stat]),
        scope: "match",
        line: matchLine,
        expected: total,
        probability: probOver(matchLine, total, model.dispersion_total),
      },
      {
        id: `${stat}_home_over`,
        label: overLabel(teamLine, STAT_LABELS[stat]),
        scope: "home",
        line: teamLine,
        expected: means.home,
        probability: probOver(teamLine, means.home, model.dispersion_team),
      },
      {
        id: `${stat}_away_over`,
        label: overLabel(teamLine, STAT_LABELS[stat]),
        scope: "away",
        line: teamLine,
        expected: means.away,
        probability: probOver(teamLine, means.away, model.dispersion_team),
      },
    );
  }

  return markets;
}
