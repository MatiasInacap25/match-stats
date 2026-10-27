import { formatDayLabel } from "./calendar";
import type { Market } from "./markets";
import type { IndexLeague, LastMatch, Meeting, SeasonSide, TeamSeason } from "./types";

const DASH = "—";
const DASH_SEP = "–";
/** Markets at or above this probability get the accent. */
const ACCENT_FROM = 0.6;

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export type SeasonSideName = "all" | "home" | "away";

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

/** Day label such as "lun 27 oct" for an ISO calendar date (YYYY-MM-DD). */
export function formatMatchDate(isoDay: string): string {
  const [year, month, day] = isoDay.split("-").map(Number);
  return formatDayLabel(new Date(year, month - 1, day));
}

/** League display name from the index; falls back to the code when it is not listed. */
export function leagueName(leagues: IndexLeague[], code: string): string {
  return leagues.find((league) => league.code === code)?.name ?? code;
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/** Three 1X2 cards; the most likely outcome carries the accent. */
export function renderOutcomes(markets: Market[]): string {
  const outcomes = ["1", "X", "2"]
    .map((id) => markets.find((market) => market.id === id))
    .filter((market): market is Market => market !== undefined);
  if (outcomes.length === 0) return "";

  const favorite = outcomes.reduce((best, market) => (market.probability > best.probability ? market : best));
  const items = outcomes
    .map(
      (market) => `<li class="outcome${market === favorite ? " is-accent" : ""}">
  <span class="outcome-label">${escapeHtml(market.label)}</span>
  <strong class="outcome-pct num">${formatPct(market.probability)}</strong>
</li>`,
    )
    .join("\n");
  return `<ul class="outcomes">\n${items}\n</ul>`;
}

/** Expected-value word agrees with the stat: "Esperadas" for tarjetas, "Esperados" otherwise. */
function expectedWord(market: Market): string {
  return market.id.startsWith("cards") ? "Esperadas" : "Esperados";
}

/** Market rows for one scope (match, home or away), each with a probability bar. */
export function renderMarketRows(markets: Market[], scope: Market["scope"]): string {
  const items = markets
    .filter((market) => market.scope === scope)
    .map((market) => {
      const accent = market.probability >= ACCENT_FROM;
      const expected =
        market.expected === null
          ? ""
          : `\n  <span class="market-exp">${expectedWord(market)}: ${formatValue(market.expected)}</span>`;
      return `<li class="market${accent ? " is-accent" : ""}">
  <span class="market-top">
    <span class="market-name">${escapeHtml(market.label)}</span>
    <strong class="market-pct num">${formatPct(market.probability)}</strong>
  </span>${expected}
  <span class="market-bar" aria-hidden="true"><span style="width:${Math.round(market.probability * 100)}%"></span></span>
</li>`;
    })
    .join("\n");
  return `<ul class="market-list">\n${items}\n</ul>`;
}

type RowKind = "count" | "avg" | "pct";
type Better = "higher" | "lower" | null;

interface SeasonRow {
  label: string;
  kind: RowKind;
  /** Which value is the better one; null rows are never bolded. */
  better: Better;
  read: (side: SeasonSide) => number | null;
}

const SEASON_ROWS: SeasonRow[] = [
  { label: "Partidos", kind: "count", better: null, read: (s) => s.matches },
  { label: "Posición", kind: "count", better: "lower", read: (s) => s.position },
  { label: "Puntos", kind: "count", better: "higher", read: (s) => s.points },
  { label: "Ganados", kind: "count", better: null, read: (s) => s.won },
  { label: "Empatados", kind: "count", better: null, read: (s) => s.drawn },
  { label: "Perdidos", kind: "count", better: null, read: (s) => s.lost },
  { label: "Goles a favor", kind: "avg", better: "higher", read: (s) => s.goals_for },
  { label: "Goles en contra", kind: "avg", better: "lower", read: (s) => s.goals_against },
  { label: "xG a favor", kind: "avg", better: "higher", read: (s) => s.xg_for },
  { label: "xG en contra", kind: "avg", better: "lower", read: (s) => s.xg_against },
  { label: "Tiros a favor", kind: "avg", better: "higher", read: (s) => s.shots_for },
  { label: "Tiros en contra", kind: "avg", better: "lower", read: (s) => s.shots_against },
  { label: "Tiros al arco a favor", kind: "avg", better: "higher", read: (s) => s.shots_on_target_for },
  { label: "Tiros al arco en contra", kind: "avg", better: "lower", read: (s) => s.shots_on_target_against },
  { label: "Córners a favor", kind: "avg", better: "higher", read: (s) => s.corners_for },
  { label: "Córners en contra", kind: "avg", better: "lower", read: (s) => s.corners_against },
  { label: "Amarillas por partido", kind: "avg", better: null, read: (s) => s.yellow_cards },
  { label: "Rojas por partido", kind: "avg", better: null, read: (s) => s.red_cards },
  { label: "Ambos marcan", kind: "pct", better: null, read: (s) => s.btts_pct },
  { label: "Más de 2.5 goles", kind: "pct", better: null, read: (s) => s.over_2_5_pct },
  { label: "Vallas invictas", kind: "count", better: null, read: (s) => s.clean_sheets },
];

function formatRowValue(kind: RowKind, value: number | null): string {
  if (kind === "pct") return formatPct(value);
  if (kind === "count") return formatValue(value, 0);
  return formatValue(value, 2);
}

/** Which side's value is bolded: only when both values exist, differ, and the row defines a better side. */
function betterSides(better: Better, home: number | null, away: number | null): [boolean, boolean] {
  if (better === null || home === null || away === null || home === away) return [false, false];
  const homeWins = better === "higher" ? home > away : home < away;
  return [homeWins, !homeWins];
}

/** Two-column season comparison: home value · label · away value, the better side in bold. */
export function renderSeasonComparison(
  home: TeamSeason,
  away: TeamSeason,
  side: SeasonSideName,
  names: [string, string],
): string {
  const rows = SEASON_ROWS.map((row) => {
    const homeValue = row.read(home[side]);
    const awayValue = row.read(away[side]);
    const [homeBetter, awayBetter] = betterSides(row.better, homeValue, awayValue);
    return `<li class="compare-row">
  <span class="compare-value num${homeBetter ? " is-better" : ""}">${formatRowValue(row.kind, homeValue)}</span>
  <span class="compare-label">${row.label}</span>
  <span class="compare-value num${awayBetter ? " is-better" : ""}">${formatRowValue(row.kind, awayValue)}</span>
</li>`;
  }).join("\n");

  return `<ul class="compare">
<li class="compare-head">
  <span class="compare-team">${escapeHtml(names[0])}</span>
  <span class="compare-label"></span>
  <span class="compare-team">${escapeHtml(names[1])}</span>
</li>
${rows}
</ul>`;
}

const RESULT_CHIPS: Record<string, string> = { W: "G", D: "E", L: "P" };

/** A team's recent matches as compact two-line rows: result, date, opponent and score, then the detail line. */
export function renderLastMatches(team: string, matches: LastMatch[]): string {
  if (matches.length === 0) return `<p class="empty">Sin partidos recientes.</p>`;

  const items = matches
    .map((match) => {
      const chip = RESULT_CHIPS[match.result] ?? DASH;
      const venue = match.venue === "H" ? "vs" : "en";
      const detail = [
        `xG ${formatValue(match.xg_for, 1)}${DASH_SEP}${formatValue(match.xg_against, 1)}`,
        `Tiros ${match.shots_for}${DASH_SEP}${match.shots_against}`,
        `Al arco ${match.shots_on_target_for}${DASH_SEP}${match.shots_on_target_against}`,
        `Córners ${match.corners_for}${DASH_SEP}${match.corners_against}`,
        `Tarjetas ${match.cards_for}${DASH_SEP}${match.cards_against}`,
      ].join(" · ");
      return `<li class="recent-item">
  <div class="recent-main">
    <span class="chip ${escapeHtml(match.result)}">${chip}</span>
    <span class="recent-date">${formatMatchDate(match.date)}</span>
    <span class="recent-opp">${venue} ${escapeHtml(match.opponent)}</span>
    <strong class="recent-score num">${match.goals_for}${DASH_SEP}${match.goals_against}</strong>
  </div>
  <p class="recent-detail num">${detail}</p>
</li>`;
    })
    .join("\n");

  return `<ul class="recent" aria-label="Últimos 6 · ${escapeHtml(team)}">
${items}
</ul>
<p class="note">Tarjetas en puntos: amarilla 1, roja 2.</p>`;
}

/** Head-to-head summary over the latest six meetings, then one compact row per meeting. */
export function renderHeadToHead(meetings: Meeting[], home: string, away: string): string {
  if (meetings.length === 0) return `<p class="empty">Sin enfrentamientos previos.</p>`;

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
  const summary = `<p class="summary">Últimos ${count}: ${escapeHtml(home)} ${plural(homeWins, "victoria", "victorias")} · ${plural(draws, "empate", "empates")} · ${escapeHtml(away)} ${plural(awayWins, "victoria", "victorias")} · ${formatValue(totalGoals / count)} goles por partido · ambos marcan ${btts}/${count}</p>`;

  const items = meetings
    .map(
      (meeting) => `<li class="recent-item">
  <div class="recent-main">
    <span class="recent-date">${formatMatchDate(meeting.date)}</span>
    <span class="recent-opp">${escapeHtml(meeting.home)} <strong class="recent-score num">${meeting.home_goals}${DASH_SEP}${meeting.away_goals}</strong> ${escapeHtml(meeting.away)}</span>
  </div>
  <p class="recent-detail num">Tiros ${meeting.home_shots}${DASH_SEP}${meeting.away_shots} · Al arco ${meeting.home_shots_on_target}${DASH_SEP}${meeting.away_shots_on_target} · Córners ${meeting.home_corners}${DASH_SEP}${meeting.away_corners} · Tarjetas ${meeting.home_cards}${DASH_SEP}${meeting.away_cards}</p>
</li>`,
    )
    .join("\n");

  return `${summary}
<ul class="recent" aria-label="Enfrentamientos entre ${escapeHtml(home)} y ${escapeHtml(away)}">
${items}
</ul>
<p class="note">Tarjetas en puntos: amarilla 1, roja 2.</p>`;
}
