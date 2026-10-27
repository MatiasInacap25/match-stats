import type { UpcomingMatch } from "./types";

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

/** Splits fixtures into the viewer's today and tomorrow, each sorted by kickoff. */
export function groupByLocalDay(
  matches: UpcomingMatch[],
  now: Date,
  timeZone: string = localTimeZone(),
): { today: UpcomingMatch[]; tomorrow: UpcomingMatch[] } {
  const today = dayKey(now, timeZone);
  const tomorrow = nextDayKey(today);
  const groups = { today: [] as UpcomingMatch[], tomorrow: [] as UpcomingMatch[] };

  const sorted = [...matches].sort((a, b) => Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc));
  for (const match of sorted) {
    const key = dayKey(new Date(match.kickoff_utc), timeZone);
    if (key === today) groups.today.push(match);
    else if (key === tomorrow) groups.tomorrow.push(match);
  }
  return groups;
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
