"use client";

import { RefreshCw, Trash2 } from "lucide-react";
import type { Bet, Performance } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn, pct } from "@/lib/utils";
import { TeamCrest } from "./team-crest";

export const tsh = (n: number) => `TSh ${Math.round(n).toLocaleString("en-US")}`;

const STATUS: Record<Bet["status"], { tag: string; sheet: string; tagCls: string }> = {
  won: { tag: "WIN", sheet: "bg-win", tagCls: "bg-green-500 text-white" },
  half_won: { tag: "HALF WIN", sheet: "bg-win", tagCls: "bg-green-500 text-white" },
  lost: { tag: "LOSE", sheet: "bg-lose", tagCls: "bg-red-500 text-white" },
  half_lost: { tag: "HALF LOSS", sheet: "bg-lose", tagCls: "bg-red-500 text-white" },
  push: { tag: "PUSH", sheet: "bg-sheet", tagCls: "bg-zinc-500 text-white" },
  open: { tag: "OPEN", sheet: "bg-sheet", tagCls: "bg-primary text-primary-foreground" },
};

function BetCard({ b, onDelete }: { b: Bet; onDelete: (id: string) => void }) {
  const s = STATUS[b.status];
  const [hs, as] = (b.score ?? ":").split(":");
  const pnl = b.payout == null ? null : b.payout - b.stake;
  return (
    <article className={cn("relative overflow-hidden rounded-[28px] text-zinc-900", s.sheet)}>
      <span className={cn("absolute left-1/2 top-0 -translate-x-1/2 rounded-b-xl px-4 py-1 text-xs font-bold", s.tagCls)}>{s.tag}</span>
      <div className="grid gap-2 p-4 pt-7">
        {[[b.home, b.home_icon, hs], [b.away, b.away_icon, as]].map(([n, icon, sc], i) => (
          <div key={i} className="flex items-center gap-3">
            <TeamCrest name={n!} icon={icon} size={40} />
            <span className="min-w-0 flex-1 truncate font-semibold uppercase">{n}</span>
            <span className="grid size-10 place-items-center rounded-full bg-white font-num text-lg font-bold">{sc || "–"}</span>
          </div>
        ))}
        <p className="text-sm text-zinc-600">{b.label}</p>
      </div>
      <div className="flex items-center gap-4 bg-white/50 px-4 py-3">
        <div><div className="text-[11px] text-zinc-500">Odds</div><div className="font-num font-semibold">{b.odds.toFixed(2)}</div></div>
        <div><div className="text-[11px] text-zinc-500">Stake</div><div className="font-num font-semibold">{tsh(b.stake)}</div></div>
        <div><div className="text-[11px] text-zinc-500">Model</div><div className="font-num font-semibold">{pct(b.p)}</div></div>
        <div className="ml-auto text-right">
          {pnl == null
            ? <><div className="text-[11px] text-zinc-500">To return</div><div className="font-num font-semibold">{tsh(b.stake * b.odds)}</div></>
            : <div className={cn("font-num text-2xl font-bold", pnl >= 0 ? "text-green-600" : "text-red-600")}>{pnl >= 0 ? "+" : "−"}{tsh(Math.abs(pnl))}</div>}
        </div>
        {b.status === "open" && <button aria-label="Remove bet" onClick={() => onDelete(b.id)} className="grid size-8 place-items-center rounded-full text-zinc-500 hover:bg-white"><Trash2 className="size-4" /></button>}
      </div>
    </article>
  );
}

export function BetsView({ bets, perf, onDelete, onSettle, settling }: {
  bets: Bet[]; perf: Performance; onDelete: (id: string) => void; onSettle: () => void; settling: boolean;
}) {
  const settled = bets.filter(b => b.payout != null);
  const staked = settled.reduce((s, b) => s + b.stake, 0);
  const pnl = settled.reduce((s, b) => s + (b.payout! - b.stake), 0);
  const won = settled.filter(b => b.status === "won" || b.status === "half_won").length;
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-3 gap-px overflow-hidden rounded-[28px] bg-border">
        {[["Profit / loss", `${pnl >= 0 ? "+" : "−"}${tsh(Math.abs(pnl))}`, pnl >= 0 ? "text-hi" : "text-destructive"],
          ["Hit rate", settled.length ? pct(won / settled.length) : "–", "text-hi"],
          ["ROI", staked ? `${((pnl / staked) * 100).toFixed(1)}%` : "–", "text-hi"]].map(([k, v, c]) => (
          <div key={k} className="bg-card p-4"><div className="text-xs text-muted-foreground">{k}</div><div className={cn("font-num text-xl font-bold", c)}>{v}</div></div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">My Bets</h2>
        <Button variant="outline" size="sm" onClick={onSettle} disabled={settling}><RefreshCw className={cn(settling && "animate-spin")} /> Settle results</Button>
      </div>
      {bets.length ? <div className="grid gap-3 md:grid-cols-2">{[...bets].reverse().map(b => <BetCard key={b.id} b={b} onDelete={onDelete} />)}</div>
        : <p className="rounded-[28px] bg-card p-6 text-center text-sm text-muted-foreground">No bets yet. Open a match, pick a selection and tap Make Bet.</p>}

      <section className="rounded-[28px] bg-card p-4">
        <h3 className="mb-1 text-base font-semibold">Model track record</h3>
        <p className="mb-3 text-xs text-muted-foreground">Every modelled price scored against final results. Lower Brier is better; ROI is a flat stake on every selection rated 50% or higher. Calibration switches on per family after 200 settled prices.</p>
        {Object.keys(perf).length ? (
          <div className="grid gap-px overflow-hidden rounded-2xl bg-border">
            {Object.entries(perf).map(([fam, v]) => (
              <div key={fam} className="grid grid-cols-4 gap-2 bg-card px-3 py-2 text-sm">
                <span className="font-semibold">{fam}</span><span className="font-num text-muted-foreground">n {v.n}</span>
                <span className="font-num">Brier {v.brier}</span><span className={cn("font-num", (v.roi_fav ?? 0) >= 0 ? "text-hi" : "text-destructive")}>ROI {v.roi_fav == null ? "–" : `${(v.roi_fav * 100).toFixed(1)}%`}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-muted-foreground">No settled results yet.</p>}
      </section>
    </div>
  );
}
