export type Theme = "dark" | "light";

/** localStorage key holding the viewer's explicit choice. */
export const THEME_STORAGE_KEY = "ms-theme";

/** A stored "dark" or "light" choice wins; anything else follows the system preference. */
export function resolveTheme(stored: string | null, prefersDark: boolean): Theme {
  if (stored === "dark" || stored === "light") return stored;
  return prefersDark ? "dark" : "light";
}
