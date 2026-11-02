import { COMPETITION_ORDER } from "./leagues";
import type { UpcomingMatch } from "./types";

/** Position of a competition in the display order; unknown codes sort after the known ones. */
function orderOf(competition: string): number {
  const position = COMPETITION_ORDER.indexOf(competition);
  return position === -1 ? COMPETITION_ORDER.length : position;
}

function byKickoff(a: UpcomingMatch, b: UpcomingMatch): number {
  return Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc);
}

function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Calendar day of `date` in `timeZone`, as YYYY-MM-DD. */
function dayKey(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function nextDayKey(key: string): string {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}

/** True when one top-5 league has both teams, so the match has probabilities and an analysis page. */
export function isAnalyzable(match: UpcomingMatch): boolean {
  return match.league !== null;
}

const UEFA_COMPETITIONS = new Set(["UCL", "UEL", "UECL"]);

/** True when both teams were matched to a league, so the match page can show each team's own data. */
export function hasTeamData(match: UpcomingMatch): boolean {
  return typeof match.home_league === "string" && typeof match.away_league === "string";
}

/** A UEFA match whose teams play in different leagues: its page shows each team from its own league. */
export function isCrossLeagueUefa(match: UpcomingMatch): boolean {
  return UEFA_COMPETITIONS.has(match.competition) && hasTeamData(match) && match.home_league !== match.away_league;
}

/** Match page URL for a cross-league UEFA match. Call only when `hasTeamData` is true. */
export function uefaMatchUrl(base: string, match: UpcomingMatch): string {
  const params = new URLSearchParams({
    competition: match.competition,
    home: match.home,
    home_league: match.home_league ?? "",
    away: match.away,
    away_league: match.away_league ?? "",
  });
  return `${base}match?${params.toString()}`;
}

/** Splits fixtures into the viewer's today and tomorrow, each sorted by kickoff. */
export function groupByLocalDay(
  matches: UpcomingMatch[],
  now: Date,
  timeZone: string = localTimeZone(),
): { today: UpcomingMatch[]; tomorrow: UpcomingMatch[] } {
  const today = dayKey(now, timeZone);
  const tomorrow = nextDayKey(today);
  const groups = { today: [] as UpcomingMatch[], tomorrow: [] as UpcomingMatch[] };

  const sorted = [...matches].sort(byKickoff);
  for (const match of sorted) {
    const key = dayKey(new Date(match.kickoff_utc), timeZone);
    if (key === today) groups.today.push(match);
    else if (key === tomorrow) groups.tomorrow.push(match);
  }
  return groups;
}

/** Competitions present in `matches`, in league order then the cup. */
export function competitionsOf(matches: UpcomingMatch[]): string[] {
  const present = new Set(matches.map((match) => match.competition));
  return [...present].sort((a, b) => orderOf(a) - orderOf(b));
}

/** Matches of the selected competitions, keeping their order. An empty selection keeps every match. */
export function filterByCompetitions(matches: UpcomingMatch[], selected: Set<string>): UpcomingMatch[] {
  if (selected.size === 0) return matches;
  return matches.filter((match) => selected.has(match.competition));
}

/** One group per competition in league order, each sorted by kickoff. */
export function groupByCompetition(matches: UpcomingMatch[]): { competition: string; matches: UpcomingMatch[] }[] {
  return competitionsOf(matches).map((competition) => ({
    competition,
    matches: matches.filter((match) => match.competition === competition).sort(byKickoff),
  }));
}

/** Day heading such as "mar 27 oct". */
export function formatDayLabel(date: Date, timeZone: string = localTimeZone()): string {
  const parts = new Intl.DateTimeFormat("es", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${value("weekday")} ${value("day")} ${value("month")}`;
}

/** Kickoff time in 24 h, such as "21:00". */
export function formatKickoff(iso: string, timeZone: string = localTimeZone()): string {
  return new Intl.DateTimeFormat("es", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
}
