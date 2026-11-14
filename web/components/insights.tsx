import type { EventPrediction } from "@/lib/types";
import { cn, pct } from "@/lib/utils";
import { TeamCrest } from "./team-crest";
import { fmtKick } from "./match-card";

const MARKET: Record<string, string> = { "1": "Match result", "18": "Total goals", "29": "Both teams to score", "45": "Correct score", "166": "Corners", "139": "Bookings", "19": "Home goals", "20": "Away goals" };

/* Sentiment: one card per fixture, one row per crowd pick with crowd vs model bars and an agreement verdict. */
export function Insights({ events, social }: { events: EventPrediction[]; social?: string }) {
  let agree = 0, total = 0;
  const sources = new Set<string>();
  const cards = events.map(e => {
    const rows = e.consensus.map(c => {
      c.sources.forEach(s => sources.add(s));
      const same = e.markets.filter(m => m.mid === c.market_id && (!c.spec || m.spec === c.spec));
      const m = same.find(r => r.desc === c.desc);
      let agrees: boolean | null = null;
      if (m) {
        const rank = [...same].sort((a, b) => b.p - a.p).indexOf(m);
        agrees = c.market_id === "1" ? rank === 0 : c.market_id === "45" ? rank < 3 : m.p >= 0.5;
        total++; if (agrees) agree++;
      }
      const label = c.market_id === "1" ? ({ Home: e.home, Draw: "Draw", Away: e.away } as Record<string, string>)[c.desc] ?? c.desc : c.desc;
      return { c, m, agrees, label };
    });
    return { e, rows };
  });

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="text-2xl font-semibold">Insights</h1>
        <p className="text-sm text-muted-foreground">Tipsters, stat models and prediction markets, grouped by pick and compared with the Jakita model.</p>
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[28px] bg-border md:grid-cols-4">
        {[["Fixtures with tips", events.length], ["Picks collected", total], ["Sources", sources.size], ["Model agrees", total ? pct(agree / total) : "–"]].map(([k, v]) => (
          <div key={String(k)} className="bg-card p-4"><div className="text-xs text-muted-foreground">{k}</div><div className="font-num text-2xl font-bold text-hi">{v}</div></div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map(({ e, rows }) => (
          <article key={e.event_id} className="overflow-hidden rounded-[28px] bg-card">
            <header className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 bg-sheet px-4 py-3 text-sheet-foreground">
              <div className="flex min-w-0 items-center gap-2 font-semibold"><TeamCrest name={e.home} icon={e.home_icon} size={30} /><span className="truncate">{e.home}</span></div>
              <div className="text-center text-[11px] text-zinc-500">{fmtKick(e.kickoff)}</div>
              <div className="flex min-w-0 flex-row-reverse items-center gap-2 text-right font-semibold"><TeamCrest name={e.away} icon={e.away_icon} size={30} /><span className="truncate">{e.away}</span></div>
            </header>
            {rows.map(({ c, m, agrees, label }, i) => (
              <div key={i} className="grid gap-2 border-t px-4 py-3 first-of-type:border-t-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">{MARKET[c.market_id] ?? "Market"}</span>
                  <span className="font-semibold">{label}</span>
                  {agrees != null && <span className={cn("ml-auto rounded-md px-2 py-0.5 text-[11px] font-bold", agrees ? "bg-good/15 text-good" : "bg-warn/15 text-warn")}>{agrees ? "Model agrees" : "Model disagrees"}</span>}
                </div>
                {[["Crowd", c.avg_prob, "bg-value"], ["Model", m?.p ?? null, "bg-primary"]].map(([k, v, color]) => (
                  <div key={String(k)} className="grid grid-cols-[48px_1fr_40px] items-center gap-2 text-xs text-muted-foreground">
                    <span>{k}</span>
                    <span className="h-1.5 overflow-hidden rounded bg-secondary"><span className={cn("block h-full", color as string)} style={{ width: `${Math.round(((v as number) ?? 0) * 100)}%` }} /></span>
                    <span className="text-right font-num text-foreground">{v == null ? (k === "Crowd" ? `${c.votes}×` : "–") : pct(v as number)}</span>
                  </div>
                ))}
                <div className="flex flex-wrap gap-1">
                  {c.sources.map(s => <span key={s} className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground">{s}</span>)}
                  {m?.odds && <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[11px] font-semibold">Odds {m.odds.toFixed(2)}</span>}
                </div>
              </div>
            ))}
          </article>
        ))}
      </div>
      {!events.length && <p className="text-muted-foreground">No sentiment collected for this snapshot. Run research from the + menu.</p>}
      {social && <p className="rounded-[28px] bg-card p-4 text-sm text-muted-foreground"><b className="text-foreground">X:</b> {social}</p>}
    </div>
  );
}
