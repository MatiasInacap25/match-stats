import { describe, expect, it } from "vitest";
import { resolveTheme } from "../src/lib/theme";

describe("resolveTheme", () => {
  it("uses a stored dark choice over the system preference", () => {
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("uses a stored light choice over the system preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
  });

  it("follows a dark system preference when nothing is stored", () => {
    expect(resolveTheme(null, true)).toBe("dark");
  });

  it("follows a light system preference when nothing is stored", () => {
    expect(resolveTheme(null, false)).toBe("light");
  });

  it("ignores an unknown stored value and follows the system", () => {
    expect(resolveTheme("blue", true)).toBe("dark");
    expect(resolveTheme("", false)).toBe("light");
  });
});
