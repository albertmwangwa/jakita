"use client";

import { Radio } from "lucide-react";
import type { EventPrediction, MarketRow } from "@/lib/types";
import { cn, pct } from "@/lib/utils";
import { TeamCrest } from "./team-crest";

export const fmtKick = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Africa/Dar_es_Salaam" });

export function predictedScore(e: EventPrediction): { score: string; p: number } | null {
  const ts = e.model?.top_scores as [string, number][] | undefined;
  if (ts?.length) return { score: ts[0][0], p: ts[0][1] };
  if (e.model?.exp_home != null) return { score: `${Math.round(e.model.exp_home)}:${Math.round(e.model.exp_away)}`, p: NaN };
  return null;
}

/** The three headline prices under a card: 1 / X / 2 (football) or 1 / 2 (basketball). */
export function headlineOdds(e: EventPrediction): MarketRow[] {
  const mid = e.sport === "football" ? "1" : "219";
  const order = ["Home", "Draw", "Away"];
  return e.markets.filter(m => m.mid === mid).sort((a, b) => order.indexOf(a.desc) - order.indexOf(b.desc));
}

const SHORT: Record<string, string> = { Home: "1", Draw: "X", Away: "2" };

export function MatchCard({ e, onOpen }: { e: EventPrediction; onOpen: () => void }) {
  const ps = predictedScore(e);
  const odds = headlineOdds(e);
  const best = odds.reduce<MarketRow | null>((b, m) => (!b || m.p > b.p ? m : b), null);
  const started = new Date(e.kickoff).getTime() <= Date.now();
  return (
    <article className="overflow-hidden rounded-[28px] bg-sheet text-sheet-foreground">
      <button onClick={onOpen} className="block w-full p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={`Open ${e.home} v ${e.away}`}>
        <div className="flex items-start justify-between gap-2">
          <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold">{e.league.split(" | ").pop()}</span>
          <span className={cn("grid size-9 place-items-center rounded-full ring-1", started ? "text-red-600 ring-red-400" : "text-zinc-500 ring-zinc-400/60")} title={started ? "Kicked off" : "Pre-match"}>
            <Radio className="size-4" />
          </span>
        </div>
        <div className="mt-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="grid justify-items-center gap-2 text-center"><TeamCrest name={e.home} icon={e.home_icon} /><span className="text-sm font-semibold uppercase leading-tight">{e.home}</span></div>
          <div className="text-center">
            <div className="font-num text-4xl font-bold tracking-tight">{ps?.score ?? "vs"}</div>
            <div className="text-xs text-zinc-500">{ps && !Number.isNaN(ps.p) ? `Predicted · ${pct(ps.p)}` : "Projected"}</div>
            <div className="mt-1 text-[11px] text-zinc-500">{fmtKick(e.kickoff)}</div>
          </div>
          <div className="grid justify-items-center gap-2 text-center"><TeamCrest name={e.away} icon={e.away_icon} /><span className="text-sm font-semibold uppercase leading-tight">{e.away}</span></div>
        </div>
      </button>
      <div className="flex gap-1.5 bg-white/40 p-2">
        {odds.map(m => (
          <div key={m.desc} className={cn("flex flex-1 items-center justify-between rounded-full bg-white px-3 py-2 text-sm", m === best && "ring-2 ring-primary")}>
            <span className="text-zinc-500">{SHORT[m.desc] ?? m.desc}</span>
            <span className="font-num font-semibold">{m.odds?.toFixed(2) ?? "–"}</span>
            <span className="font-num text-[11px] text-zinc-500">{pct(m.p)}</span>
          </div>
        ))}
      </div>
    </article>
  );
}
