import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import { probOver } from "../src/lib/probability";
import {
  MATCH_LINES,
  TEAM_LINES,
  TeamNotFoundError,
  matchMarkets,
  type Market,
} from "../src/lib/markets";
import type { LeagueData } from "../src/lib/types";

const league: LeagueData = E0;

function find(markets: Market[], id: string): Market {
  const market = markets.find((candidate) => candidate.id === id);
  if (!market) throw new Error(`missing market ${id}`);
  return market;
}

function expectClose(actual: number, expected: number, tolerance = 1e-9): void {
  expect(Math.abs(actual - expected)).toBeLessThan(tolerance);
}

describe("matchMarkets", () => {
  it("builds 1X2, BTTS and goal markets from the example", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");

    const result = ["1", "X", "2"].map((id) => find(markets, id).probability);
    expectClose(result.reduce((sum, p) => sum + p, 0), 1);

    for (const market of markets) {
      expect(market.probability).toBeGreaterThan(0);
      expect(market.probability).toBeLessThan(1);
    }

    expect(find(markets, "btts").probability).toBeGreaterThan(0);
    expect(find(markets, "goals_over").line).toBe(2.5);
    expect(find(markets, "goals_home_over").line).toBe(1.5);
    expect(find(markets, "goals_away_over").line).toBe(1.5);
  });

  it("uses the Global Constraints lines", () => {
    expect(MATCH_LINES).toEqual({
      goals: 2.5,
      corners: 9.5,
      cards: 4.5,
      shots: 24.5,
      shots_on_target: 8.5,
    });
    expect(TEAM_LINES).toEqual({
      goals: 1.5,
      corners: 4.5,
      cards: 1.5,
      shots: 12.5,
      shots_on_target: 4.5,
    });
  });

  it("computes stat expected values and probabilities", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");

    const cornersHome = 5.6 * 1.2 * 1.1;
    const cornersAway = 4.6 * 0.9 * 0.8;

    const homeCorners = find(markets, "corners_home_over");
    expect(homeCorners.scope).toBe("home");
    expect(homeCorners.line).toBe(4.5);
    expectClose(homeCorners.expected ?? NaN, cornersHome);
    expectClose(homeCorners.probability, probOver(4.5, cornersHome, 12.0));

    const awayCorners = find(markets, "corners_away_over");
    expect(awayCorners.scope).toBe("away");
    expectClose(awayCorners.expected ?? NaN, cornersAway);
    expectClose(awayCorners.probability, probOver(4.5, cornersAway, 12.0));

    const matchCorners = find(markets, "corners_over");
    expect(matchCorners.scope).toBe("match");
    expect(matchCorners.line).toBe(9.5);
    expectClose(matchCorners.expected ?? NaN, cornersHome + cornersAway);
    expectClose(matchCorners.probability, probOver(9.5, cornersHome + cornersAway, 15.0));
  });

  it("uses Poisson for cards because the example dispersion is null", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const cardsHome = 2.0 * 1.2 * 1.1;
    const cardsAway = 2.2 * 0.9 * 0.8;

    expectClose(
      find(markets, "cards_over").probability,
      probOver(4.5, cardsHome + cardsAway, null),
    );
    expectClose(find(markets, "cards_home_over").probability, probOver(1.5, cardsHome, null));
  });

  it("uses Spanish market labels without the team name in team rows", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");

    expect(find(markets, "1").label).toBe("Gana local");
    expect(find(markets, "X").label).toBe("Empate");
    expect(find(markets, "2").label).toBe("Gana visita");
    expect(find(markets, "btts").label).toBe("Ambos marcan");
    expect(find(markets, "goals_over").label).toBe("Más de 2.5 goles");
    expect(find(markets, "goals_home_over").label).toBe("Más de 1.5 goles");
    expect(find(markets, "corners_over").label).toBe("Más de 9.5 córners");
    expect(find(markets, "corners_away_over").label).toBe("Más de 4.5 córners");
    expect(find(markets, "cards_over").label).toBe("Más de 4.5 tarjetas");
    expect(find(markets, "cards_home_over").label).toBe("Más de 1.5 tarjetas");
    expect(find(markets, "shots_over").label).toBe("Más de 24.5 tiros");
    expect(find(markets, "shots_home_over").label).toBe("Más de 12.5 tiros");
    expect(find(markets, "shots_on_target_over").label).toBe("Más de 8.5 tiros al arco");
    expect(find(markets, "shots_on_target_away_over").label).toBe("Más de 4.5 tiros al arco");
  });

  it("throws TeamNotFoundError for a team missing from the league", () => {
    expect(() => matchMarkets(league, "Arsenal", "Nowhere FC")).toThrow(TeamNotFoundError);
    expect(() => matchMarkets(league, "Nowhere FC", "Brighton")).toThrow(TeamNotFoundError);
  });
});
