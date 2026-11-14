"use client";

import { useMemo, useState } from "react";
import { BarChart3, Dribbble, Goal, LayoutGrid, Ticket, X } from "lucide-react";
import type { LeagueEntry } from "@/lib/data";
import { cn } from "@/lib/utils";
import { LeagueFlag } from "./league-flag";

const TOP = ["UEFA Nations League", "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", "UEFA Champions League",
  "UEFA Europa League", "Int. Friendly Games", "Africa Cup of Nations", "CONCACAF Nations League", "Brasileiro Serie A", "Liga MX", "MLS", "NBA", "Euroleague", "Liga ACB"];

export type Nav = { view: string; sport: string; league: string; date: string };

export function Sidebar({ nav, go, leagues, days, counts, meta, open, onClose }: {
  nav: Nav; go: (p: Partial<Nav> & { view?: string }) => void; leagues: LeagueEntry[]; days: { date: string; n: number }[];
  counts: Record<string, number>; meta: { generated: string }; open: boolean; onClose: () => void;
}) {
  const [lq, setLq] = useState("");
  const { top, groups, total } = useMemo(() => {
    const f = leagues.filter(l => !lq || l.league.toLowerCase().includes(lq.toLowerCase()));
    const top = f.filter(l => TOP.some(t => l.name.includes(t))).sort((a, b) => b.n - a.n);
    const groups = new Map<string, LeagueEntry[]>();
    for (const l of f) groups.set(l.country, [...(groups.get(l.country) ?? []), l]);
    return { top, groups: [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0])), total: leagues.reduce((s, l) => s + l.n, 0) };
  }, [leagues, lq]);

  const item = (active: boolean) => cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground", active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground");
  const sections: [string, string, string | null, React.ElementType, number | null][] = [
    ["fixtures", "Football", "football", Goal, counts.football ?? null],
    ["fixtures", "Basketball", "basketball", Dribbble, counts.basketball ?? null],
    ["bets", "My Bets", null, Ticket, null],
    ["insights", "Insights", null, BarChart3, null],
  ];
  const label = (d: string) => new Date(d + "T12:00:00+03:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

  return (
    <>
      <div className={cn("fixed inset-0 z-30 bg-black/50 lg:hidden", open ? "block" : "hidden")} onClick={onClose} />
      <aside aria-label="Navigation" className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-72 flex-col gap-5 overflow-y-auto border-r bg-card px-3 pb-8 pt-5 transition-transform lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex items-start justify-between px-2">
          <div><div className="font-display text-xl font-bold tracking-tight">JAKITA<span className="text-hi">.</span></div>
            <div className="text-xs text-muted-foreground">Snapshot {meta.generated.replace("T", " ")} EAT</div></div>
          <button aria-label="Close menu" onClick={onClose} className="grid size-8 place-items-center rounded-full bg-secondary lg:hidden"><X className="size-4" /></button>
        </div>

        <nav className="grid gap-0.5" aria-label="Sections">
          {sections.map(([view, text, sport, Icon, n]) => {
            const active = nav.view === view && (!sport || nav.sport === sport);
            return (
              <button key={text} className={item(active)} aria-current={active ? "page" : undefined}
                onClick={() => go(sport ? { view, sport, league: "", date: "" } : { view })}>
                <Icon className="size-[18px]" />{text}{n != null && <span className="ml-auto font-num text-xs opacity-70">{n}</span>}
              </button>
            );
          })}
        </nav>

        {nav.view === "fixtures" && (
          <>
            <div>
              <h3 className="px-2 pb-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Days</h3>
              <div className="flex flex-wrap gap-1.5 px-1">
                <button onClick={() => go({ date: "" })} className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", !nav.date && "border-foreground bg-foreground text-background")}>All 7 days</button>
                {days.map(d => (
                  <button key={d.date} onClick={() => go({ date: d.date })} className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", nav.date === d.date && "border-foreground bg-foreground text-background")}>
                    {label(d.date)} <span className="opacity-60">{d.n}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-2">
              <h3 className="px-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Leagues · {leagues.length}</h3>
              <input aria-label="Find a league" placeholder="Find a league or country" value={lq} onChange={e => setLq(e.target.value)}
                className="h-9 rounded-full bg-secondary px-4 text-sm outline-none ring-primary focus:ring-1" />
              <div className="grid gap-px">
                <LeagueBtn active={!nav.league} onClick={() => go({ league: "" })} icon={<LayoutGrid className="size-4 text-muted-foreground" />} name="All leagues" n={total} />
                {top.length > 0 && <div className="px-3 pb-1 pt-3 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Top leagues</div>}
                {top.map(l => <LeagueBtn key={"t" + l.league} active={nav.league === l.league} onClick={() => go({ league: l.league })} icon={<LeagueFlag flag={l.flag} kind={l.kind} />} name={l.name} sub={l.country} n={l.n} />)}
                {groups.map(([c, ls]) => (
                  <div key={c} className="grid gap-px">
                    <div className="flex items-center gap-2 px-3 pb-1 pt-3 text-[11px] font-bold uppercase tracking-widest text-muted-foreground"><LeagueFlag flag={ls[0].flag} kind={ls[0].kind} />{c}</div>
                    {ls.sort((a, b) => b.n - a.n).map(l => <LeagueBtn key={l.league} active={nav.league === l.league} onClick={() => go({ league: l.league })} icon={null} name={l.name} n={l.n} />)}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  );
}

function LeagueBtn({ active, onClick, icon, name, sub, n }: { active: boolean; onClick: () => void; icon: React.ReactNode; name: string; sub?: string; n: number }) {
  return (
    <button onClick={onClick} aria-current={active ? "true" : undefined} title={sub ? `${sub} · ${name}` : name}
      className={cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-left text-[13px] text-muted-foreground hover:bg-secondary hover:text-foreground", !icon && "pl-10", active && "bg-accent font-bold text-accent-foreground")}>
      {icon}<span className="min-w-0 flex-1 truncate">{name}</span><span className="font-num text-xs opacity-70">{n}</span>
    </button>
  );
}
