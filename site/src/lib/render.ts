import type { Market } from "./markets";
import type { IndexLeague, LastMatch, Meeting, SeasonSide, TeamSeason } from "./types";

const DASH = "—";

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

/** Plain number with fixed digits. `null` and non-finite values render as a dash. */
export function formatValue(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits);
}

/** 0–1 fraction as a whole percentage, e.g. 0.62 → "62%". */
export function formatPct(fraction: number | null): string {
  if (fraction === null || !Number.isFinite(fraction)) return DASH;
  return `${Math.round(fraction * 100)}%`;
}

/** League display name from the index; falls back to the code when it is not listed. */
export function leagueName(leagues: IndexLeague[], code: string): string {
  return leagues.find((league) => league.code === code)?.name ?? code;
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

type RowKind = "count" | "avg" | "pct";

interface SeasonRow {
  label: string;
  kind: RowKind;
  read: (side: SeasonSide) => number | null;
}

const SEASON_ROWS: SeasonRow[] = [
  { label: "Matches", kind: "count", read: (s) => s.matches },
  { label: "Position", kind: "count", read: (s) => s.position },
  { label: "Points", kind: "count", read: (s) => s.points },
  { label: "Won", kind: "count", read: (s) => s.won },
  { label: "Drawn", kind: "count", read: (s) => s.drawn },
  { label: "Lost", kind: "count", read: (s) => s.lost },
  { label: "Goals for", kind: "avg", read: (s) => s.goals_for },
  { label: "Goals against", kind: "avg", read: (s) => s.goals_against },
  { label: "xG for", kind: "avg", read: (s) => s.xg_for },
  { label: "xG against", kind: "avg", read: (s) => s.xg_against },
  { label: "Shots for", kind: "avg", read: (s) => s.shots_for },
  { label: "Shots against", kind: "avg", read: (s) => s.shots_against },
  { label: "Shots on target for", kind: "avg", read: (s) => s.shots_on_target_for },
  { label: "Shots on target against", kind: "avg", read: (s) => s.shots_on_target_against },
  { label: "Corners for", kind: "avg", read: (s) => s.corners_for },
  { label: "Corners against", kind: "avg", read: (s) => s.corners_against },
  { label: "Yellow cards", kind: "avg", read: (s) => s.yellow_cards },
  { label: "Red cards", kind: "avg", read: (s) => s.red_cards },
  { label: "BTTS", kind: "pct", read: (s) => s.btts_pct },
  { label: "Over 2.5 goals", kind: "pct", read: (s) => s.over_2_5_pct },
  { label: "Clean sheets", kind: "count", read: (s) => s.clean_sheets },
];

function formatRowValue(kind: RowKind, value: number | null): string {
  if (kind === "pct") return formatPct(value);
  if (kind === "count") return formatValue(value, 0);
  return formatValue(value, 2);
}

export function renderMarkets(markets: Market[], home: string, away: string): string {
  const sections: { title: string; scope: Market["scope"] }[] = [
    { title: "Match", scope: "match" },
    { title: home, scope: "home" },
    { title: away, scope: "away" },
  ];

  return sections
    .map(({ title, scope }) => {
      const items = markets
        .filter((market) => market.scope === scope)
        .map(
          (market) => `<li>
  <span class="market-label">${escapeHtml(market.label)}</span>
  <strong class="market-probability">${formatPct(market.probability)}</strong>
  <span class="market-expected">${market.expected === null ? "" : `exp. ${formatValue(market.expected)}`}</span>
</li>`,
        )
        .join("\n");
      return `<section class="markets">
<h2>${escapeHtml(title)}</h2>
<ul class="market-list">
${items}
</ul>
</section>`;
    })
    .join("\n");
}

export function renderSeasonTable(
  home: TeamSeason,
  away: TeamSeason,
  side: "all" | "home" | "away",
  names: [string, string],
): string {
  const header = names.map((name) => `<th scope="col">${escapeHtml(name)}</th>`).join("");
  const rows = SEASON_ROWS.map((row) => {
    const homeValue = formatRowValue(row.kind, row.read(home[side]));
    const awayValue = formatRowValue(row.kind, row.read(away[side]));
    return `<tr><th scope="row">${row.label}</th><td>${homeValue}</td><td>${awayValue}</td></tr>`;
  }).join("\n");

  return `<table class="season-table">
<thead><tr><th scope="col">Stat</th>${header}</tr></thead>
<tbody>
${rows}
</tbody>
</table>`;
}

export function renderLastMatches(team: string, matches: LastMatch[]): string {
  if (matches.length === 0) return `<p class="empty">No recent matches for ${escapeHtml(team)}.</p>`;

  const rows = matches
    .map(
      (match) => `<tr>
  <td>${escapeHtml(match.date)}</td>
  <td>${match.venue === "H" ? "vs" : "at"} ${escapeHtml(match.opponent)}</td>
  <td>${match.goals_for}-${match.goals_against}</td>
  <td>${escapeHtml(match.result)}</td>
  <td>${formatValue(match.xg_for, 1)}-${formatValue(match.xg_against, 1)}</td>
  <td>${match.shots_for}-${match.shots_against}</td>
  <td>${match.shots_on_target_for}-${match.shots_on_target_against}</td>
  <td>${match.corners_for}-${match.corners_against}</td>
  <td>${match.cards_for}-${match.cards_against}</td>
</tr>`,
    )
    .join("\n");

  return `<div class="scroll">
<table class="last-table">
<thead><tr><th scope="col">Date</th><th scope="col">Opponent</th><th scope="col">Score</th><th scope="col">Result</th><th scope="col">xG</th><th scope="col">Shots</th><th scope="col">SoT</th><th scope="col">Corners</th><th scope="col">Cards</th></tr></thead>
<tbody>
${rows}
</tbody>
</table>
</div>
<p class="note">Cards are points (yellow 1, red 2).</p>`;
}

export function renderHeadToHead(meetings: Meeting[], home: string, away: string): string {
  if (meetings.length === 0) return `<p class="empty">No previous meetings.</p>`;

  const recent = meetings.slice(0, 6);
  let homeWins = 0;
  let draws = 0;
  let awayWins = 0;
  let totalGoals = 0;
  let btts = 0;

  for (const meeting of recent) {
    const homeGoals = meeting.home === home ? meeting.home_goals : meeting.away_goals;
    const awayGoals = meeting.home === home ? meeting.away_goals : meeting.home_goals;
    if (homeGoals > awayGoals) homeWins++;
    else if (homeGoals === awayGoals) draws++;
    else awayWins++;
    totalGoals += meeting.home_goals + meeting.away_goals;
    if (meeting.home_goals > 0 && meeting.away_goals > 0) btts++;
  }

  const count = recent.length;
  const summary = `<p class="summary">Last ${count} ${count === 1 ? "meeting" : "meetings"}:
${escapeHtml(home)} ${plural(homeWins, "win", "wins")} ·
${plural(draws, "draw", "draws")} ·
${escapeHtml(away)} ${plural(awayWins, "win", "wins")} ·
Avg goals ${formatValue(totalGoals / count)} ·
BTTS ${btts}/${count}</p>`;

  const rows = meetings
    .map(
      (meeting) => `<tr>
  <td>${escapeHtml(meeting.date)}</td>
  <td>${escapeHtml(meeting.league)}</td>
  <td>${escapeHtml(meeting.home)}</td>
  <td>${meeting.home_goals}-${meeting.away_goals}</td>
  <td>${escapeHtml(meeting.away)}</td>
  <td>${meeting.home_shots}-${meeting.away_shots}</td>
  <td>${meeting.home_shots_on_target}-${meeting.away_shots_on_target}</td>
  <td>${meeting.home_corners}-${meeting.away_corners}</td>
  <td>${meeting.home_cards}-${meeting.away_cards}</td>
</tr>`,
    )
    .join("\n");

  return `${summary}
<div class="scroll">
<table class="h2h-table">
<thead><tr><th scope="col">Date</th><th scope="col">League</th><th scope="col">Home</th><th scope="col">Score</th><th scope="col">Away</th><th scope="col">Shots</th><th scope="col">SoT</th><th scope="col">Corners</th><th scope="col">Cards</th></tr></thead>
<tbody>
${rows}
</tbody>
</table>
</div>`;
}
