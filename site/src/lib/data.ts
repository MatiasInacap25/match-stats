/// <reference types="astro/client" />
import type { H2HData, IndexData, LeagueData } from "./types";

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
