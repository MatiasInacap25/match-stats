import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import H2H from "../../contract/example/h2h/E0.json";
import type { LeagueData, H2HData } from "../src/lib/types";
import {
  formatPct,
  formatValue,
  renderHeadToHead,
  renderLastMatches,
  renderMarkets,
  renderSeasonTable,
} from "../src/lib/render";
import { matchMarkets } from "../src/lib/markets";

const league: LeagueData = E0;
const h2h: H2HData = H2H;

function rowFor(html: string, label: string): string {
  const match = html.match(new RegExp(`<tr><th scope="row">${label}</th>(.*?)</tr>`));
  if (!match) throw new Error(`missing row ${label}`);
  return match[1];
}

describe("formatValue and formatPct", () => {
  it("renders null and non-finite values as a dash", () => {
    expect(formatValue(null)).toBe("—");
    expect(formatValue(NaN)).toBe("—");
    expect(formatValue(Infinity)).toBe("—");
  });

  it("renders finite values with the given digits", () => {
    expect(formatValue(2.5)).toBe("2.50");
    expect(formatValue(2.456, 1)).toBe("2.5");
  });

  it("renders fractions as whole percentages", () => {
    expect(formatPct(0.62)).toBe("62%");
  });
});

describe("renderSeasonTable", () => {
  it("renders a dash for null xG", () => {
    const html = renderSeasonTable(
      league.teams.Arsenal.season,
      league.teams.Chelsea.season,
      "away",
      ["Arsenal", "Chelsea"],
    );
    expect(rowFor(html, "xG for")).toContain("—");
    expect(rowFor(html, "xG for")).toContain("1.90");
    expect(html).not.toContain("NaN");
  });
});

describe("renderMarkets", () => {
  it("renders every market with its percentage and escapes team names", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarkets(markets, "Arsenal", "Brighton");
    expect(html).toContain("Over 2.5 goals");
    expect(html).toContain("Arsenal Over 1.5 goals");
    expect(html).not.toContain("NaN");

    const escaped = renderMarkets(markets, "A&B", "<Brighton>");
    expect(escaped).toContain("A&amp;B");
    expect(escaped).not.toContain("<Brighton>");
  });
});

describe("renderLastMatches", () => {
  it("renders the team's recent matches", () => {
    const html = renderLastMatches("Arsenal", league.teams.Arsenal.last6);
    expect(html).toContain("Brighton");
    expect(html).toContain("2-1");
  });

  it("says so when there are no matches", () => {
    expect(renderLastMatches("Arsenal", [])).toContain("No recent matches");
  });
});

describe("renderHeadToHead", () => {
  it("shows an empty message when there are no meetings", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Chelsea"], "Arsenal", "Chelsea");
    expect(html).toContain("No previous meetings");
  });

  it("summarises the meetings", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Brighton"], "Arsenal", "Brighton");
    expect(html).toContain("Arsenal 1 win");
    expect(html).toContain("Brighton 0 wins");
    expect(html).toContain("1 draw");
    expect(html).toContain("Avg goals 2.50");
    expect(html).toContain("BTTS 2/2");
  });
});
