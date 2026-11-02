import { afterEach, describe, expect, it, vi } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import { loadUefa } from "../src/lib/data";
import { probOver } from "../src/lib/probability";
import {
  MATCH_LINES,
  TEAM_LINES,
  TeamNotFoundError,
  crossLeagueAvailable,
  crossLeagueMarkets,
  matchMarkets,
  type CrossLeagueSide,
  type Market,
} from "../src/lib/markets";
import type { LeagueData, UefaData, UefaOffset } from "../src/lib/types";

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

/** A copy of the example league under another code; `cornersScale` multiplies its corner averages. */
function leagueAs(code: string, cornersScale = 1): LeagueData {
  const copy: LeagueData = structuredClone(E0);
  copy.league = code;
  if (copy.stats) {
    copy.stats.corners.avg_home *= cornersScale;
    copy.stats.corners.avg_away *= cornersScale;
  }
  return copy;
}

function uefaWith(offsets: Record<string, UefaOffset> = {}): UefaData {
  return {
    calibrated: true,
    home_advantage: E0.goals.home_advantage,
    offsets: { E0: { attack: 0, defense: 0 }, SP1: { attack: 0, defense: 0 }, ...offsets },
    seasons: [2025],
    backtest: {
      held_out: 2025,
      matches: 189,
      log_loss: 0.99,
      log_loss_unadjusted: 1.02,
      log_loss_baseline: 1.07,
    },
  };
}

function side(name: string, code: string, league: LeagueData): CrossLeagueSide {
  return { name, code, league };
}

describe("crossLeagueMarkets", () => {
  it("matches the league model when offsets are zero and both teams share the league", () => {
    const markets = crossLeagueMarkets(side("Arsenal", "E0", E0), side("Brighton", "E0", E0), uefaWith());
    const expected = matchMarkets(E0, "Arsenal", "Brighton");

    for (const id of ["1", "X", "2", "btts", "goals_over", "corners_over", "shots_home_over"]) {
      expectClose(find(markets, id).probability, find(expected, id).probability);
    }
  });

  it("raises the home win probability when the home league's attack offset is positive", () => {
    const away = leagueAs("SP1");
    const base = crossLeagueMarkets(side("Arsenal", "E0", E0), side("Brighton", "SP1", away), uefaWith());
    const boosted = crossLeagueMarkets(
      side("Arsenal", "E0", E0),
      side("Brighton", "SP1", away),
      uefaWith({ E0: { attack: 0.2, defense: 0 } }),
    );

    expect(find(boosted, "1").probability).toBeGreaterThan(find(base, "1").probability);
  });

  it("builds corners from each team's own league, pooled by geometric mean", () => {
    const awayLeague = leagueAs("SP1", 2);
    const markets = crossLeagueMarkets(side("Arsenal", "E0", E0), side("Brighton", "SP1", awayLeague), uefaWith());

    const homeCorners = E0.stats.corners;
    const awayCorners = awayLeague.stats!.corners;
    const expectedHome =
      Math.sqrt(homeCorners.avg_home * awayCorners.avg_home) *
      homeCorners.teams.Arsenal.home_for *
      awayCorners.teams.Brighton.away_against;
    const expectedAway =
      Math.sqrt(homeCorners.avg_away * awayCorners.avg_away) *
      awayCorners.teams.Brighton.away_for *
      homeCorners.teams.Arsenal.home_against;

    expectClose(find(markets, "corners_home_over").expected ?? NaN, expectedHome);
    expectClose(find(markets, "corners_away_over").expected ?? NaN, expectedAway);
    expectClose(find(markets, "corners_over").expected ?? NaN, expectedHome + expectedAway);
    // Both leagues share dispersion 15.0 for the match total, so the pooled value is 15.0.
    expectClose(find(markets, "corners_over").probability, probOver(9.5, expectedHome + expectedAway, 15.0));
  });

  it("hides stat markets when either league has no stats and keeps the goal markets", () => {
    const goalsOnly = leagueAs("NOR");
    delete goalsOnly.stats;

    const markets = crossLeagueMarkets(
      side("Arsenal", "E0", E0),
      side("Brighton", "NOR", goalsOnly),
      uefaWith({ NOR: { attack: 0, defense: 0 } }),
    );

    expect(markets.some((market) => /^(corners|shots|cards)/.test(market.id))).toBe(false);
    expect(find(markets, "1").probability).toBeGreaterThan(0);
    expect(find(markets, "goals_over").probability).toBeGreaterThan(0);
  });

  it("throws TeamNotFoundError for a team missing from its league", () => {
    expect(() =>
      crossLeagueMarkets(side("Nowhere FC", "E0", E0), side("Brighton", "SP1", leagueAs("SP1")), uefaWith()),
    ).toThrow(TeamNotFoundError);
  });
});

describe("crossLeagueAvailable", () => {
  it("is true for a calibrated model whose offsets hold both leagues", () => {
    expect(crossLeagueAvailable(uefaWith(), "E0", "SP1")).toBe(true);
  });

  it("is false without uefa data", () => {
    expect(crossLeagueAvailable(null, "E0", "SP1")).toBe(false);
  });

  it("is false when the model is not calibrated", () => {
    expect(crossLeagueAvailable({ ...uefaWith(), calibrated: false }, "E0", "SP1")).toBe(false);
  });

  it("is false when either league is missing from the offsets", () => {
    const uefa = uefaWith();
    expect(crossLeagueAvailable(uefa, "E0", "T1")).toBe(false);
    expect(crossLeagueAvailable(uefa, "T1", "E0")).toBe(false);
  });
});

describe("loadUefa", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null on a 404", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    expect(await loadUefa()).toBeNull();
  });

  it("returns null on invalid JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{not json")));
    expect(await loadUefa()).toBeNull();
  });

  it("returns null when the JSON has no offsets", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ calibrated: true }))));
    expect(await loadUefa()).toBeNull();
  });

  it("returns the parsed model", async () => {
    const uefa = uefaWith();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(uefa))));
    expect(await loadUefa()).toEqual(uefa);
  });
});
