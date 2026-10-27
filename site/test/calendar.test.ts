import { describe, expect, it } from "vitest";
import { formatDayLabel, formatKickoff, groupByLocalDay } from "../src/lib/calendar";
import type { UpcomingMatch } from "../src/lib/types";

const NOW = new Date("2026-10-27T12:00:00Z");

function match(kickoff_utc: string, home = "Arsenal", away = "Brighton"): UpcomingMatch {
  return { league: "E0", kickoff_utc, home, away };
}

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

describe("formatKickoff", () => {
  it("formats the kickoff time in 24 h in the given time zone", () => {
    expect(formatKickoff("2026-10-27T20:00:00Z", "Europe/Madrid")).toBe("21:00");
  });

  it("keeps two-digit hours and minutes", () => {
    expect(formatKickoff("2026-10-27T20:00:00Z", "Europe/London")).toBe("20:00");
    expect(formatKickoff("2026-10-27T08:05:00Z", "Europe/London")).toBe("08:05");
  });
});
