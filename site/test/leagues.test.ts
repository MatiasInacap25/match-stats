import { describe, expect, it } from "vitest";
import { COMPETITION_ORDER, LEAGUE_SHORT_NAMES, shortName } from "../src/lib/leagues";

describe("LEAGUE_SHORT_NAMES", () => {
  it("names the seven leagues, the three UEFA cups and the DFB-Pokal", () => {
    expect(LEAGUE_SHORT_NAMES).toEqual({
      E0: "Premier",
      SP1: "LaLiga",
      I1: "Serie A",
      D1: "Bundesliga",
      F1: "Ligue 1",
      E1: "Championship",
      P1: "Liga Portugal",
      UCL: "Champions",
      UEL: "Europa League",
      UECL: "Conference",
      DFB: "DFB-Pokal",
    });
  });
});

describe("COMPETITION_ORDER", () => {
  it("lists the leagues in contract order, then the UEFA cups, then the cup", () => {
    expect(COMPETITION_ORDER).toEqual(["E0", "SP1", "I1", "D1", "F1", "E1", "P1", "UCL", "UEL", "UECL", "DFB"]);
  });
});

describe("shortName", () => {
  it("returns the short name for a known competition", () => {
    expect(shortName("I1", "Serie A TIM")).toBe("Serie A");
    expect(shortName("DFB", "DFB-Pokal")).toBe("DFB-Pokal");
  });

  it("names the UEFA competitions", () => {
    expect(shortName("UCL", "Champions League")).toBe("Champions");
    expect(shortName("UEL", "Europa League")).toBe("Europa League");
    expect(shortName("UECL", "Conference League")).toBe("Conference");
  });

  it("falls back to the given name for an unknown competition", () => {
    expect(shortName("XYZ", "Some Cup")).toBe("Some Cup");
  });

  it("does not read inherited object keys as competitions", () => {
    expect(shortName("constructor", "Fallback")).toBe("Fallback");
    expect(shortName("toString", "Fallback")).toBe("Fallback");
  });
});
