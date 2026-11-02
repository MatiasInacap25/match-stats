/** Short competition names, keyed by the codes used in the data (`competition` and `league`). */
export const LEAGUE_SHORT_NAMES: Record<string, string> = {
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
};

/** Display order everywhere: the leagues in contract order, then the UEFA cups, then the DFB-Pokal. */
export const COMPETITION_ORDER: readonly string[] = [
  "E0",
  "SP1",
  "I1",
  "D1",
  "F1",
  "E1",
  "P1",
  "UCL",
  "UEL",
  "UECL",
  "DFB",
];

/** Short name for a competition code, or `fallback` when the code is unknown. */
export function shortName(code: string, fallback: string): string {
  return Object.hasOwn(LEAGUE_SHORT_NAMES, code) ? LEAGUE_SHORT_NAMES[code] : fallback;
}
