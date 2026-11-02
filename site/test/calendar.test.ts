import { describe, expect, it } from "vitest";
import {
  chipCompetitions,
  competitionsOf,
  filterByCompetitions,
  formatDayLabel,
  formatKickoff,
  groupByCompetition,
  groupByLocalDay,
  hasTeamData,
  isAnalyzable,
  isCrossLeagueUefa,
  uefaMatchUrl,
} from "../src/lib/calendar";
import type { UpcomingMatch } from "../src/lib/types";

const NOW = new Date("2026-10-27T12:00:00Z");

function match(kickoff_utc: string, home = "Arsenal", away = "Brighton"): UpcomingMatch {
  return {
    competition: "E0",
    competition_name: "Premier League",
    kickoff_utc,
    home,
    away,
    league: "E0",
  };
}

function cupMatch(kickoff_utc: string, league: string | null): UpcomingMatch {
  return {
    competition: "DFB",
    competition_name: "DFB-Pokal",
    kickoff_utc,
    home: "Hamburg",
    away: "Ein Frankfurt",
    league,
  };
}

describe("isAnalyzable", () => {
  it("is true when one top-5 league has both teams", () => {
    expect(isAnalyzable(match("2026-10-27T18:00:00Z"))).toBe(true);
    expect(isAnalyzable(cupMatch("2026-10-27T18:00:00Z", "D1"))).toBe(true);
  });

  it("is false when no single league has both teams", () => {
    expect(isAnalyzable(cupMatch("2026-10-27T18:00:00Z", null))).toBe(false);
  });

  it("is false for a UEFA match with no league having both teams", () => {
    const ucl: UpcomingMatch = {
      competition: "UCL",
      competition_name: "Champions League",
      kickoff_utc: "2026-10-27T18:00:00Z",
      home: "Benfica",
      away: "Galatasaray",
      league: null,
    };

    expect(isAnalyzable(ucl)).toBe(false);
  });
});

describe("groupByLocalDay", () => {
  it("splits matches into today and tomorrow in the given time zone", () => {
    const matches = [
      match("2026-10-27T18:00:00Z", "A", "B"),
      match("2026-10-28T10:00:00Z", "C", "D"),
    ];

    const groups = groupByLocalDay(matches, NOW, "Europe/Madrid");

    expect(groups.today.map((m) => m.home)).toEqual(["A"]);
    expect(groups.tomorrow.map((m) => m.home)).toEqual(["C"]);
  });

  it("uses the viewer's local date of kickoff, not the UTC date", () => {
    // 23:30 UTC on Oct 27 is 00:30 on Oct 28 in Madrid, but 20:30 on Oct 27 in Santiago.
    const late = match("2026-10-27T23:30:00Z", "Late", "Game");

    expect(groupByLocalDay([late], NOW, "Europe/Madrid").tomorrow).toEqual([late]);
    expect(groupByLocalDay([late], NOW, "Europe/Madrid").today).toEqual([]);
    expect(groupByLocalDay([late], NOW, "America/Santiago").today).toEqual([late]);
    expect(groupByLocalDay([late], NOW, "America/Santiago").tomorrow).toEqual([]);
  });

  it("excludes matches on other days", () => {
    const matches = [
      match("2026-10-26T20:00:00Z", "Yesterday", "X"),
      match("2026-10-27T20:00:00Z", "Today", "X"),
      match("2026-10-28T20:00:00Z", "Tomorrow", "X"),
      match("2026-10-29T20:00:00Z", "Later", "X"),
    ];

    const groups = groupByLocalDay(matches, NOW, "Europe/Madrid");

    expect(groups.today.map((m) => m.home)).toEqual(["Today"]);
    expect(groups.tomorrow.map((m) => m.home)).toEqual(["Tomorrow"]);
  });

  it("sorts each group by kickoff", () => {
    const matches = [
      match("2026-10-27T20:00:00Z", "Late", "X"),
      match("2026-10-27T15:00:00Z", "Early", "X"),
    ];

    const groups = groupByLocalDay(matches, NOW, "Europe/Madrid");

    expect(groups.today.map((m) => m.home)).toEqual(["Early", "Late"]);
  });

  it("keeps cup matches without an analysis league in their day", () => {
    const groups = groupByLocalDay(
      [cupMatch("2026-10-27T18:00:00Z", null), cupMatch("2026-10-28T18:00:00Z", "D1")],
      NOW,
      "Europe/Madrid",
    );

    expect(groups.today.map((m) => m.league)).toEqual([null]);
    expect(groups.tomorrow.map((m) => m.league)).toEqual(["D1"]);
  });

  it("returns empty groups when there are no matches", () => {
    expect(groupByLocalDay([], NOW, "Europe/Madrid")).toEqual({ today: [], tomorrow: [] });
  });
});

describe("formatDayLabel", () => {
  it("formats a Spanish weekday, day and short month", () => {
    // 26 Oct 2026 is a Monday.
    expect(formatDayLabel(new Date("2026-10-26T12:00:00Z"), "Europe/Madrid")).toBe("lun 26 oct");
  });

  it("uses the given time zone for the calendar day", () => {
    // Midnight UTC on Oct 27 is still Oct 26 in Santiago (UTC-3).
    expect(formatDayLabel(new Date("2026-10-27T00:30:00Z"), "America/Santiago")).toBe("lun 26 oct");
  });
});

function inCompetition(competition: string, kickoff_utc: string, home = competition): UpcomingMatch {
  return {
    competition,
    competition_name: competition,
    kickoff_utc,
    home,
    away: "Opponent",
    league: competition === "DFB" ? null : competition,
  };
}

describe("competitionsOf", () => {
  it("returns the competitions present, in league order with the cup last", () => {
    const matches = [
      inCompetition("DFB", "2026-10-27T18:00:00Z"),
      inCompetition("P1", "2026-10-27T19:00:00Z"),
      inCompetition("I1", "2026-10-27T17:00:00Z"),
      inCompetition("I1", "2026-10-27T20:00:00Z"),
      inCompetition("E0", "2026-10-27T16:00:00Z"),
    ];

    expect(competitionsOf(matches)).toEqual(["E0", "I1", "P1", "DFB"]);
  });

  it("puts the UEFA cups after the leagues and before the DFB-Pokal", () => {
    const matches = [
      inCompetition("DFB", "2026-10-27T18:00:00Z"),
      inCompetition("UECL", "2026-10-27T18:00:00Z"),
      inCompetition("E0", "2026-10-27T16:00:00Z"),
      inCompetition("UCL", "2026-10-27T21:00:00Z"),
      inCompetition("UEL", "2026-10-27T21:00:00Z"),
    ];

    expect(competitionsOf(matches)).toEqual(["E0", "UCL", "UEL", "UECL", "DFB"]);
  });

  it("returns an empty list when there are no matches", () => {
    expect(competitionsOf([])).toEqual([]);
  });
});

describe("chipCompetitions", () => {
  it("adds selected competitions that have no match that day, in league order", () => {
    const matches = [inCompetition("E0", "2026-10-27T16:00:00Z"), inCompetition("SP1", "2026-10-27T19:00:00Z")];

    expect(chipCompetitions(matches, new Set(["UCL"]))).toEqual(["E0", "SP1", "UCL"]);
  });

  it("does not duplicate a selected competition that has matches", () => {
    const matches = [inCompetition("E0", "2026-10-27T16:00:00Z"), inCompetition("SP1", "2026-10-27T19:00:00Z")];

    expect(chipCompetitions(matches, new Set(["SP1"]))).toEqual(["E0", "SP1"]);
  });

  it("equals competitionsOf when nothing is selected", () => {
    const matches = [
      inCompetition("DFB", "2026-10-27T18:00:00Z"),
      inCompetition("UCL", "2026-10-27T21:00:00Z"),
      inCompetition("E0", "2026-10-27T16:00:00Z"),
    ];

    expect(chipCompetitions(matches, new Set())).toEqual(competitionsOf(matches));
  });
});

describe("filterByCompetitions", () => {
  const matches = [
    inCompetition("E0", "2026-10-27T16:00:00Z"),
    inCompetition("I1", "2026-10-27T17:00:00Z"),
    inCompetition("DFB", "2026-10-27T18:00:00Z"),
  ];

  it("keeps every match when the selection is empty", () => {
    expect(filterByCompetitions(matches, new Set())).toEqual(matches);
  });

  it("keeps only the matches of the selected competitions, in their order", () => {
    const result = filterByCompetitions(matches, new Set(["DFB", "E0"]));

    expect(result.map((m) => m.competition)).toEqual(["E0", "DFB"]);
  });

  it("returns an empty list when no match belongs to the selection", () => {
    expect(filterByCompetitions(matches, new Set(["P1"]))).toEqual([]);
  });

  it("keeps only the matches of the selected UEFA and league competitions", () => {
    const withCup = [
      inCompetition("UCL", "2026-10-27T21:00:00Z"),
      inCompetition("E0", "2026-10-27T16:00:00Z"),
      inCompetition("UEL", "2026-10-27T18:00:00Z"),
    ];

    const result = filterByCompetitions(withCup, new Set(["UCL", "E0"]));

    expect(result.map((m) => m.competition)).toEqual(["UCL", "E0"]);
  });
});

describe("groupByCompetition", () => {
  it("groups by competition in league order, with kickoff order inside each group", () => {
    const matches = [
      inCompetition("DFB", "2026-10-27T18:00:00Z"),
      inCompetition("I1", "2026-10-27T20:00:00Z", "Late"),
      inCompetition("E0", "2026-10-27T19:00:00Z"),
      inCompetition("I1", "2026-10-27T15:00:00Z", "Early"),
    ];

    const groups = groupByCompetition(matches);

    expect(groups.map((group) => group.competition)).toEqual(["E0", "I1", "DFB"]);
    expect(groups[1].matches.map((m) => m.home)).toEqual(["Early", "Late"]);
  });

  it("returns no groups when there are no matches", () => {
    expect(groupByCompetition([])).toEqual([]);
  });
});

describe("formatKickoff", () => {
  it("formats the kickoff time in 24 h in the given time zone", () => {
    expect(formatKickoff("2026-10-27T20:00:00Z", "Europe/Madrid")).toBe("21:00");
  });

  it("keeps two-digit hours and minutes", () => {
    expect(formatKickoff("2026-10-27T20:00:00Z", "Europe/London")).toBe("20:00");
    expect(formatKickoff("2026-10-27T08:05:00Z", "Europe/London")).toBe("08:05");
  });
});

function uefa(overrides: Partial<UpcomingMatch> = {}): UpcomingMatch {
  return {
    competition: "UCL",
    competition_name: "Champions League",
    kickoff_utc: "2026-10-27T18:00:00Z",
    home: "Barcelona",
    away: "Aston Villa",
    league: null,
    home_league: "SP1",
    away_league: "E0",
    ...overrides,
  };
}

describe("hasTeamData", () => {
  it("is true when both teams have a league", () => {
    expect(hasTeamData(uefa())).toBe(true);
  });

  it("is false when either league is null or missing", () => {
    expect(hasTeamData(uefa({ home_league: null }))).toBe(false);
    expect(hasTeamData(uefa({ away_league: null }))).toBe(false);
    expect(hasTeamData({ ...uefa(), home_league: undefined, away_league: undefined })).toBe(false);
  });
});

describe("isCrossLeagueUefa", () => {
  it("is true for a UEFA match whose teams come from different leagues", () => {
    expect(isCrossLeagueUefa(uefa())).toBe(true);
  });

  it("is false for a UEFA match between teams of the same league", () => {
    expect(isCrossLeagueUefa(uefa({ home_league: "E0", away_league: "E0" }))).toBe(false);
  });

  it("is false for a domestic or cup match", () => {
    expect(isCrossLeagueUefa(cupMatch("2026-10-27T18:00:00Z", "D1"))).toBe(false);
  });
});

describe("uefaMatchUrl", () => {
  it("builds the UEFA match page URL with each team and its league", () => {
    expect(uefaMatchUrl("/", uefa())).toBe(
      "/match?competition=UCL&home=Barcelona&home_league=SP1&away=Aston+Villa&away_league=E0",
    );
  });
});
