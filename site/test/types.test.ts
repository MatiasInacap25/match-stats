import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import H2H from "../../contract/example/h2h/E0.json";
import INDEX from "../../contract/example/index.json";
import type { H2HData, IndexData, LeagueData } from "../src/lib/types";

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
