import { promises as fs } from "fs";
import path from "path";
import type { EventPrediction, Predictions } from "./types";

// The Python pipeline writes ../data/predictions/<day>.json (override with JAKITA_ROOT).
export const ROOT = process.env.JAKITA_ROOT ?? path.resolve(process.cwd(), "..");
const DIR = path.join(ROOT, "data", "predictions");

export async function listDays(): Promise<string[]> {
  try {
    return (await fs.readdir(DIR)).filter(f => f.endsWith(".json")).map(f => f.replace(".json", "")).sort().reverse();
  } catch {
    return [];
  }
}

// The file can be tens of MB for a 7-day window: parse once per (day, mtime).
const cache = new Map<string, { mtime: number; data: Predictions }>();

export async function loadDay(day: string): Promise<Predictions | null> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const file = path.join(DIR, `${day}.json`);
  try {
    const { mtimeMs } = await fs.stat(file);
    const hit = cache.get(day);
    if (hit && hit.mtime === mtimeMs) return hit.data;
    const data = JSON.parse(await fs.readFile(file, "utf-8")) as Predictions;
    cache.set(day, { mtime: mtimeMs, data });
    return data;
  } catch {
    return null;
  }
}

export type LeagueEntry = { league: string; country: string; name: string; n: number; flag?: string | null; kind?: string };
export type BoardQuery = { sport: string; league?: string; date?: string; q?: string };

const HEADLINE = new Set(["1", "219"]);
export const TOP_LEAGUES = ["UEFA Nations League", "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
  "UEFA Champions League", "UEFA Europa League", "Int. Friendly Games", "Africa Cup of Nations", "CONCACAF Nations League",
  "Brasileiro Serie A", "Liga MX", "MLS", "NBA", "Euroleague", "Liga ACB"];

/** List view payload: filtered events with markets trimmed to the 1X2 / moneyline rows. */
export function board(data: Predictions, q: BoardQuery) {
  const all = data.sports[q.sport]?.events ?? [];
  const inDay = all.filter(e => !q.date || e.kickoff.startsWith(q.date));
  const leagues = new Map<string, LeagueEntry>();
  for (const e of inDay) {
    const l = leagues.get(e.league) ?? { league: e.league, country: e.league.split(" | ")[0], name: e.league.split(" | ").slice(1).join(" | "), n: 0, flag: e.flag, kind: e.league_kind };
    l.n++;
    leagues.set(e.league, l);
  }
  const days = new Map<string, number>();
  for (const e of all) days.set(e.kickoff.slice(0, 10), (days.get(e.kickoff.slice(0, 10)) ?? 0) + 1);
  const text = (q.q ?? "").toLowerCase();
  const events = inDay
    .filter(e => (!q.league || e.league === q.league) && (!text || `${e.home} ${e.away} ${e.league}`.toLowerCase().includes(text)))
    .sort((a, b) => a.kickoff.localeCompare(b.kickoff));
  const trim = (e: EventPrediction): EventPrediction => ({ ...e, markets: e.markets.filter(m => HEADLINE.has(m.mid)) });
  const featured = events.filter(e => e.depth === "full" && new Date(e.kickoff).getTime() > Date.now())
    .sort((a, b) => b.coverage.markets - a.coverage.markets)[0] ?? events[0];
  return {
    leagues: [...leagues.values()],
    days: [...days.entries()].sort().map(([date, n]) => ({ date, n })),
    total: events.length,
    events: events.slice(0, 300).map(trim),
    featured: featured ? trim(featured) : null,
    counts: Object.fromEntries(Object.entries(data.sports).map(([s, v]) => [s, v.events.length])),
  };
}

export function findEvent(data: Predictions, id: string): EventPrediction | null {
  for (const s of Object.values(data.sports)) {
    const e = s.events.find(x => x.event_id === id);
    if (e) return e;
  }
  return null;
}

export function sentiment(data: Predictions) {
  return Object.values(data.sports).flatMap(s => s.events)
    .filter(e => e.consensus?.length)
    .map(e => ({ ...e, markets: e.markets.filter(m => e.consensus.some(c => c.market_id === m.mid)) }));
}
