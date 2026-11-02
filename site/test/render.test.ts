import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import H2H from "../../contract/example/h2h/E0.json";
import type { H2HData, IndexLeague, LastMatch, LeagueData, TeamSeason } from "../src/lib/types";
import { matchMarkets, type Market } from "../src/lib/markets";
import {
  formatMatchDate,
  formatPct,
  formatValue,
  leagueName,
  renderHeadToHead,
  renderLastMatches,
  renderMarketRows,
  renderOutcomes,
  renderSeasonComparison,
} from "../src/lib/render";

const league: LeagueData = E0;
const h2h: H2HData = H2H;

/** The `<li>` that holds `label`, so assertions stay inside one row. */
function itemFor(html: string, label: string): string {
  const item = html.split("<li").find((segment) => segment.includes(`>${label}</span>`));
  if (!item) throw new Error(`missing item ${label}`);
  return item;
}

function makeMarket(id: string, probability: number, scope: Market["scope"] = "match"): Market {
  return { id, label: `Mercado ${id}`, scope, line: null, expected: null, probability };
}

function cloneSeason(): TeamSeason {
  return structuredClone(league.teams.Arsenal.season);
}

describe("formatValue, formatPct and formatMatchDate", () => {
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

  it("formats an ISO date as a Spanish day label", () => {
    expect(formatMatchDate("2026-10-27")).toBe("mar 27 oct");
  });
});

describe("renderOutcomes", () => {
  it("renders the three 1X2 cards with Spanish labels", () => {
    const markets = [makeMarket("1", 0.2), makeMarket("X", 0.3), makeMarket("2", 0.5)];
    const html = renderOutcomes([
      { ...markets[0], label: "Gana local" },
      { ...markets[1], label: "Empate" },
      { ...markets[2], label: "Gana visita" },
    ]);
    expect(html).toContain("Gana local");
    expect(html).toContain("Empate");
    expect(html).toContain("Gana visita");
    expect(html).toContain("50%");
  });

  it("test favorite gets accent class", () => {
    const html = renderOutcomes([
      { ...makeMarket("1", 0.2), label: "Gana local" },
      { ...makeMarket("X", 0.3), label: "Empate" },
      { ...makeMarket("2", 0.5), label: "Gana visita" },
    ]);
    const accented = html.split("<li").filter((segment) => segment.includes("is-accent"));
    expect(accented).toHaveLength(1);
    expect(accented[0]).toContain("Gana visita");
  });
});

describe("renderMarketRows", () => {
  it("renders Spanish labels with the expected line and a probability bar", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarketRows(markets, "match");
    expect(html).toContain("Más de 2.5 goles");
    expect(html).toContain(`Esperados: ${formatValue(markets.find((m) => m.id === "goals_over")?.expected ?? null)}`);
    expect(html).toContain("width:");
    expect(html).not.toContain("NaN");
  });

  it("uses the feminine expected word for cards", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarketRows(markets, "match");
    expect(itemFor(html, "Más de 4.5 tarjetas")).toContain("Esperadas:");
    expect(itemFor(html, "Más de 9.5 córners")).toContain("Esperados:");
  });

  it("omits the expected line when there is no mean", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarketRows(markets, "match");
    expect(itemFor(html, "Ambos marcan")).not.toContain("Esperad");
  });

  it("omits the 1X2 outcomes from the match rows, which the outcome cards already show", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarketRows(markets, "match");
    expect(html).not.toContain("Gana local");
    expect(html).not.toContain("Empate");
    expect(html).not.toContain("Gana visita");
    expect(html).toContain("Ambos marcan");
    expect(html).toContain("Más de 2.5 goles");
    expect(renderOutcomes(markets)).toContain("Gana local");
  });

  it("renders only the markets of the requested scope", () => {
    const markets = matchMarkets(league, "Arsenal", "Brighton");
    const html = renderMarketRows(markets, "home");
    expect(html).toContain("Más de 1.5 goles");
    expect(html).not.toContain("Más de 2.5 goles");
  });

  it("test market ≥ 60% gets accent class", () => {
    const html = renderMarketRows([makeMarket("a", 0.6), makeMarket("b", 0.59)], "match");
    const accented = html.split("<li").filter((segment) => segment.includes("is-accent"));
    expect(accented).toHaveLength(1);
    expect(accented[0]).toContain("60%");
    expect(html).toContain("width:60%");
  });
});

describe("renderSeasonComparison", () => {
  it("test season comparison bolds the better side (position lower is better)", () => {
    const home = cloneSeason();
    const away = cloneSeason();
    home.all.position = 5;
    away.all.position = 2;
    const html = renderSeasonComparison(home, away, "all", ["Arsenal", "Brighton"]);
    const item = itemFor(html, "Posición");
    expect(item).toContain('is-better">2</span>');
    expect(item).not.toContain('is-better">5</span>');
  });

  it("bolds the higher value for for-stats and the lower for against-stats", () => {
    const home = cloneSeason();
    const away = cloneSeason();
    home.all.goals_for = 2;
    away.all.goals_for = 1;
    home.all.goals_against = 0.5;
    away.all.goals_against = 1.5;
    const html = renderSeasonComparison(home, away, "all", ["Arsenal", "Brighton"]);
    expect(itemFor(html, "Goles a favor")).toContain('is-better">2.00</span>');
    expect(itemFor(html, "Goles en contra")).toContain('is-better">0.50</span>');
    expect(itemFor(html, "Goles en contra")).not.toContain('is-better">1.50</span>');
  });

  it("renders a dash for null values and never bolds them", () => {
    const home = cloneSeason();
    const away = cloneSeason();
    home.all.xg_for = null;
    away.all.xg_for = 1.2;
    const html = renderSeasonComparison(home, away, "all", ["Arsenal", "Brighton"]);
    const item = itemFor(html, "xG a favor");
    expect(item).toContain("—");
    expect(item).not.toContain('is-better">—</span>');
    expect(html).not.toContain("NaN");
  });

  it("uses the requested side of the season", () => {
    const home = cloneSeason();
    const away = cloneSeason();
    home.home.goals_for = 3;
    home.all.goals_for = 1;
    const html = renderSeasonComparison(home, away, "home", ["Arsenal", "Brighton"]);
    expect(itemFor(html, "Goles a favor")).toContain("3.00");
  });

  it("escapes team names in the header", () => {
    const html = renderSeasonComparison(cloneSeason(), cloneSeason(), "all", ["A&B", "<C>"]);
    expect(html).toContain("A&amp;B");
    expect(html).not.toContain("<C>");
  });
});

describe("renderLastMatches", () => {
  const [first] = league.teams.Arsenal.last6;

  it("renders the result chip, date, venue, score and detail line", () => {
    const html = renderLastMatches("Arsenal", league.teams.Arsenal.last6);
    expect(html).toContain("Brighton");
    expect(html).toContain("2–1");
    expect(html).toContain('chip W">G</span>');
    expect(html).toContain("25 oct");
    expect(html).toContain("xG 1.8–0.9");
    expect(html).toContain("Tiros 17–9");
    expect(html).toContain("Tarjetas en puntos: amarilla 1, roja 2.");
  });

  it("circles L for home matches, labelled Local", () => {
    const html = renderLastMatches("Arsenal", [{ ...first, venue: "H" }]);
    expect(html).toContain('<span class="venue" role="img" aria-label="Local" title="Local">');
    expect(html).toContain('<span aria-hidden="true">L</span></span>');
  });

  it("circles V for away matches, labelled Visitante", () => {
    const html = renderLastMatches("Arsenal", [{ ...first, venue: "A" }]);
    expect(html).toContain('<span class="venue" role="img" aria-label="Visitante" title="Visitante">');
    expect(html).toContain('<span aria-hidden="true">V</span></span>');
  });

  it("no longer prefixes the opponent with 'vs' or 'en'", () => {
    const home = renderLastMatches("Arsenal", [{ ...first, venue: "H" }]);
    const away = renderLastMatches("Arsenal", [{ ...first, venue: "A" }]);
    expect(home).not.toMatch(/>(vs|en) /);
    expect(away).not.toMatch(/>(vs|en) /);
  });

  it("keeps the square result chip next to the venue circle", () => {
    const html = renderLastMatches("Arsenal", [{ ...first, venue: "A" }]);
    expect(html).toContain('chip W">G</span>');
    expect(html).toContain('class="venue"');
  });

  it("renders a dash when xG is missing", () => {
    const missing: LastMatch = { ...first, xg_for: null };
    expect(renderLastMatches("Arsenal", [missing])).toContain("xG —–0.9");
  });

  it("says so when there are no matches", () => {
    expect(renderLastMatches("Arsenal", [])).toContain("Sin partidos recientes.");
  });
});

/** A goals-only team (Bodø/Glimt style): every season and last-6 stat is null. */
function goalsOnlySeason(): TeamSeason {
  const season = structuredClone(league.teams.Arsenal.season);
  for (const side of [season.all, season.home, season.away]) {
    Object.assign(side, {
      xg_for: null,
      xg_against: null,
      shots_for: null,
      shots_against: null,
      shots_on_target_for: null,
      shots_on_target_against: null,
      corners_for: null,
      corners_against: null,
      yellow_cards: null,
      red_cards: null,
    });
  }
  return season;
}

/** Goals-only last-6 row: every stat is null, as the contract says. */
function goalsOnlyMatch(match: LastMatch): LastMatch {
  return {
    ...match,
    xg_for: null,
    xg_against: null,
    shots_for: null,
    shots_against: null,
    shots_on_target_for: null,
    shots_on_target_against: null,
    corners_for: null,
    corners_against: null,
    cards_for: null,
    cards_against: null,
  };
}

describe("goals-only teams", () => {
  const [first] = league.teams.Arsenal.last6;

  it("shows a dash for every missing season stat and never NaN", () => {
    const html = renderSeasonComparison(goalsOnlySeason(), league.teams.Arsenal.season, "all", ["Bodø/Glimt", "Arsenal"]);
    expect(html).not.toContain("NaN");
    expect(itemFor(html, "xG a favor")).toContain('compare-value num">—</span>');
    expect(itemFor(html, "Tiros a favor")).toContain('compare-value num">—</span>');
    expect(itemFor(html, "Córners a favor")).toContain('compare-value num">—</span>');
    expect(itemFor(html, "Amarillas por partido")).toContain('compare-value num">—</span>');
    expect(itemFor(html, "Goles a favor")).not.toContain("—");
  });

  it("keeps the score and result of a last-6 row with no stat data, and hides the stat line", () => {
    const html = renderLastMatches("Bodø/Glimt", [goalsOnlyMatch(first)]);
    expect(html).not.toContain("NaN");
    expect(html).toContain(`${first.goals_for}–${first.goals_against}`);
    expect(html).toContain('chip W">G</span>');
    expect(html).not.toContain("xG ");
    expect(html).not.toContain("Tiros ");
  });

  it("renders a dash for each missing stat in a partly filled row", () => {
    const partial: LastMatch = { ...first, xg_for: null };
    const html = renderLastMatches("Arsenal", [partial]);
    expect(html).toContain("xG —–0.9");
    expect(html).not.toContain("NaN");
  });
});

describe("renderHeadToHead", () => {
  it("has no venue circle", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Chelsea"], "Arsenal", "Chelsea");
    expect(html).not.toContain('class="venue"');
    expect(html).not.toContain("aria-label=\"Local\"");
    expect(html).not.toContain("aria-label=\"Visitante\"");
  });

  it("shows an empty message when there are no meetings", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Chelsea"], "Arsenal", "Chelsea");
    expect(html).toContain("Sin enfrentamientos previos.");
  });

  it("summarises the meetings in Spanish", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Brighton"], "Arsenal", "Brighton");
    expect(html).toContain("Arsenal 1 victoria");
    expect(html).toContain("Brighton 0 victorias");
    expect(html).toContain("1 empate");
    expect(html).toContain("2.50 goles por partido");
    expect(html).toContain("ambos marcan 2/2");
  });

  it("shows the score and the detail line per meeting", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Brighton"], "Arsenal", "Brighton");
    const row = html.split("<li").find((segment) => segment.includes("1 mar"));
    if (!row) throw new Error("missing 2026-03-01 row");
    expect(row).toContain("Brighton");
    expect(row).toContain("Arsenal");
    expect(row).toContain("Tiros 10–15");
    expect(row).toContain("Al arco 3–6");
    expect(row).toContain("Córners 4–6");
    expect(row).toContain("Tarjetas 3–1");
  });

  it("shows the year next to each meeting date", () => {
    const html = renderHeadToHead(h2h.pairs["Arsenal|Brighton"], "Arsenal", "Brighton");
    expect(html).toContain("1 mar 2026");
    expect(html).toContain("14 sept 2025");
  });
});

describe("leagueName", () => {
  const leagues: IndexLeague[] = [{ code: "E0", name: "Premier League", teams: [] }];

  it("returns the league name from the index", () => {
    expect(leagueName(leagues, "E0")).toBe("Premier League");
  });

  it("falls back to the code when the league is missing", () => {
    expect(leagueName(leagues, "SP1")).toBe("SP1");
    expect(leagueName([], "E0")).toBe("E0");
  });
});
