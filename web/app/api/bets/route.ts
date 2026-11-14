import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { ROOT } from "@/lib/data";
import type { Bet } from "@/lib/types";

const BETS = path.join(ROOT, "data", "bets.json");
const PERF = path.join(ROOT, "data", "performance.json");

async function read<T>(p: string, fallback: T): Promise<T> {
  try { return JSON.parse(await fs.readFile(p, "utf-8")); } catch { return fallback; }
}

export async function GET() {
  return NextResponse.json({ bets: await read<Bet[]>(BETS, []), performance: await read(PERF, {}) });
}

// Same schema the Python tracker settles (jakita/tracker.py).
export async function POST(req: Request) {
  const b = await req.json();
  const stake = Number(b.stake);
  if (!b.event_id || !b.mid || !b.desc || !(Number(b.odds) > 1) || !(stake > 0)) {
    return NextResponse.json({ error: "Pick and a positive stake are required." }, { status: 400 });
  }
  const bets = await read<Bet[]>(BETS, []);
  const bet: Bet = {
    id: `b${bets.length + 1}-${Date.now()}`, event_id: b.event_id, sport: b.sport, match: b.match, home: b.home, away: b.away,
    kickoff: b.kickoff, home_icon: b.home_icon, away_icon: b.away_icon, label: b.label, mid: b.mid, spec: b.spec ?? "",
    desc: b.desc, odds: Number(b.odds), p: Number(b.p), stake, status: "open", payout: null,
    placed_at: new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 16),
  };
  bets.push(bet);
  await fs.mkdir(path.dirname(BETS), { recursive: true });
  await fs.writeFile(BETS, JSON.stringify(bets, null, 1));
  return NextResponse.json(bet);
}

export async function DELETE(req: Request) {
  const id = new URL(req.url).searchParams.get("id");
  const bets = (await read<Bet[]>(BETS, [])).filter(b => !(b.id === id && b.status === "open"));
  await fs.writeFile(BETS, JSON.stringify(bets, null, 1));
  return NextResponse.json({ ok: true });
}
