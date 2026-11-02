/// <reference types="astro/client" />
import type { H2HData, IndexData, LeagueData, UefaData } from "./types";

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${path}`);
  if (!response.ok) throw new Error(`Failed to load ${path}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export function loadIndex(): Promise<IndexData> {
  return loadJson<IndexData>("index.json");
}

export function loadLeague(code: string): Promise<LeagueData> {
  return loadJson<LeagueData>(`leagues/${encodeURIComponent(code)}.json`);
}

export function loadHeadToHead(code: string): Promise<H2HData> {
  return loadJson<H2HData>(`h2h/${encodeURIComponent(code)}.json`);
}

function isUefaData(value: unknown): value is UefaData {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<UefaData>;
  return typeof candidate.calibrated === "boolean" && typeof candidate.offsets === "object" && candidate.offsets !== null;
}

/** uefa.json, or null when it is missing, unreadable or malformed. UEFA matches then have no probabilities. */
export async function loadUefa(): Promise<UefaData | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}data/uefa.json`);
    if (!response.ok) return null;
    const parsed: unknown = await response.json();
    return isUefaData(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
