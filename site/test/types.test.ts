import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import H2H from "../../contract/example/h2h/E0.json";
import INDEX from "../../contract/example/index.json";
import type { H2HData, IndexData, LeagueData, UefaData, UpcomingMatch } from "../src/lib/types";

describe("contract types", () => {
  it("accepts a goals-only league file with no stats key", () => {
    const goalsOnly: LeagueData = {
      league: "NOR",
      season: "2026",
      goals: { home_advantage: 0.2, rho: -0.1, teams: {} },
      teams: {},
    };
    expect(goalsOnly.stats).toBeUndefined();
  });

  it("accepts an upcoming UEFA fixture with home_league and away_league", () => {
    const fixture = {
      competition: "UCL",
      competition_name: "Champions League",
      kickoff_utc: "2026-11-03T20:00:00Z",
      home: "Bodø/Glimt",
      away: "Arsenal",
      league: null,
      home_league: "NOR",
      away_league: "E0",
    } satisfies UpcomingMatch;
    expect(fixture.home_league).toBe("NOR");
  });

  it("accepts a uefa.json payload with offsets, seasons and backtest", () => {
    const uefa = {
      calibrated: true,
      home_advantage: 0.21,
      offsets: { E0: { attack: 0.0, defense: 0.0 }, T1: { attack: -0.18, defense: 0.15 } },
      seasons: [2023, 2024, 2025],
      backtest: { held_out: 2025, matches: 189, log_loss: 0.99, log_loss_unadjusted: 1.02, log_loss_baseline: 1.07 },
    } satisfies UefaData;
    expect(uefa.offsets.T1.defense).toBe(0.15);
  });
});

describe("contract example files", () => {
  it("index.json satisfies IndexData", () => {
    const index = INDEX satisfies IndexData;
    expect(index.leagues[0].code).toBe("E0");
  });

  it("leagues/E0.json satisfies LeagueData", () => {
    const league = E0 satisfies LeagueData;
    expect(league.teams.Arsenal.season.all.matches).toBe(9);
    expect(league.teams.Chelsea.season.away.xg_for).toBeNull();
  });

  it("h2h/E0.json satisfies H2HData", () => {
    const h2h = H2H satisfies H2HData;
    expect(h2h.pairs["Arsenal|Brighton"]).toHaveLength(2);
  });
});
