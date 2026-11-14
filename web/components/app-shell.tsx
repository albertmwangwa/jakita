"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2, Menu, Plus, Search, X } from "lucide-react";
import type { Bet, EventPrediction, Performance, Pick } from "@/lib/types";
import type { LeagueEntry } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { cn, pct } from "@/lib/utils";
import { MatchCard, fmtKick, predictedScore } from "./match-card";
import { MatchDetail } from "./match-detail";
import { BetsView, tsh } from "./bets-view";
import { RunButton } from "./run-button";
import { TeamCrest } from "./team-crest";
import { LeagueFlag } from "./league-flag";
import { Sidebar, type Nav } from "./sidebar";
import { Insights } from "./insights";

type Board = {
  leagues: LeagueEntry[]; days: { date: string; n: number }[]; total: number; events: EventPrediction[];
  featured: EventPrediction | null; counts: Record<string, number>;
};

export function AppShell(props: {
  meta: { generated: string; source: string; windowHours: number; social?: string };
  days: string[]; day: string; view: "fixtures" | "bets" | "insights"; sport: string; league: string; date: string; q: string;
  board: Board; sentiment: EventPrediction[];
}) {
  const { meta, day, view, sport, league, date, board } = props;
  const router = useRouter();
  const pathname = usePathname();
  const [menu, setMenu] = useState(false);
  const [q, setQ] = useState(props.q);
  const [runOpen, setRunOpen] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EventPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [slip, setSlip] = useState<{ e: EventPrediction; p: Pick } | null>(null);
  const [stake, setStake] = useState("5000");
  const [bets, setBets] = useState<Bet[]>([]);
  const [perf, setPerf] = useState<Performance>({});
  const [settling, setSettling] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function go(p: Partial<Nav> & { q?: string }) {
    const next = { view, sport, league, date, q, ...p };
    const s = new URLSearchParams({ day });
    for (const [k, v] of Object.entries(next)) if (v && !(k === "view" && v === "fixtures")) s.set(k, String(v));
    setOpenId(null); setDetail(null); setMenu(false);
    router.push(`${pathname}?${s.toString()}`);
  }

  async function loadBets() {
    const j = await fetch("/api/bets").then(r => r.json()).catch(() => ({ bets: [], performance: {} }));
    setBets(j.bets); setPerf(j.performance);
  }
  useEffect(() => { loadBets(); }, []);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 3000); return () => clearTimeout(t); } }, [toast]);
  useEffect(() => { const t = setTimeout(() => { if (q !== props.q) go({ q }); }, 350); return () => clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  async function open(e: EventPrediction) {
    setOpenId(e.event_id); setLoading(true); setDetail(null);
    const res = await fetch(`/api/event?day=${day}&id=${encodeURIComponent(e.event_id)}`);
    setDetail(res.ok ? await res.json() : null); setLoading(false);
    window.scrollTo({ top: 0 });
  }

  async function placeBet() {
    if (!slip || !slip.p.odds) return;
    const { e, p } = slip;
    const res = await fetch("/api/bets", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...p, stake: Number(stake), event_id: e.event_id, sport: e.sport, match: `${e.home} v ${e.away}`, home: e.home, away: e.away, kickoff: e.kickoff, home_icon: e.home_icon, away_icon: e.away_icon }),
    });
    if (res.ok) { setSlip(null); setToast("Bet added to My Bets"); loadBets(); }
    else setToast((await res.json()).error ?? "Could not add the bet");
  }
  async function settle() {
    setSettling(true);
    const j = await fetch("/api/settle", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ day }) }).then(r => r.json());
    setSettling(false); setToast(j.ok ? "Results checked" : "Settlement failed: " + String(j.error).slice(0, 120)); loadBets();
  }
  async function del(id: string) { await fetch(`/api/bets?id=${encodeURIComponent(id)}`, { method: "DELETE" }); loadBets(); }

  const openStake = bets.filter(b => b.status === "open").reduce((s, b) => s + b.stake, 0);
  const pnl = bets.reduce((s, b) => s + (b.payout == null ? 0 : b.payout - b.stake), 0);
  const groups = new Map<string, EventPrediction[]>();
  for (const e of board.events) groups.set(e.league, [...(groups.get(e.league) ?? []), e]);
  const leagueMeta = new Map(board.leagues.map(l => [l.league, l]));
  const activeLeague = league ? leagueMeta.get(league) : undefined;

  return (
    <div className="min-h-screen lg:pl-72">
      <Sidebar nav={{ view, sport, league, date }} go={go} leagues={board.leagues} days={board.days} counts={board.counts}
        meta={meta} open={menu} onClose={() => setMenu(false)} />

      <div className="mx-auto max-w-5xl px-4 pb-24 pt-4 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 mb-5 flex items-center justify-between gap-3 bg-background/90 px-4 py-3 backdrop-blur lg:-mx-8 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button aria-label="Open menu" onClick={() => setMenu(true)} className="grid size-10 place-items-center rounded-full bg-card lg:hidden"><Menu className="size-5" /></button>
            <select aria-label="Snapshot" className="h-9 rounded-full bg-card px-3 text-xs font-semibold" value={day} onChange={e => router.push(`/?day=${e.target.value}`)}>
              {props.days.map(d => <option key={d} value={d}>Snapshot {d}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-1.5 rounded-full bg-card p-1 pl-4">
            <span className="font-num text-sm font-semibold" title="Open stakes · settled profit">{tsh(openStake)}<span className={cn("ml-2 text-xs", pnl >= 0 ? "text-hi" : "text-destructive")}>{pnl >= 0 ? "+" : "−"}{tsh(Math.abs(pnl)).replace("TSh ", "")}</span></span>
            <button aria-label="Update predictions" onClick={() => setRunOpen(!runOpen)} className="grid size-9 place-items-center rounded-full bg-primary text-primary-foreground"><Plus className="size-5" /></button>
            <label className="relative hidden sm:block">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-hi" />
              <input aria-label="Search teams" placeholder="Search team" value={q} onChange={e => setQ(e.target.value)} className="h-9 w-48 rounded-full bg-secondary pl-9 pr-3 text-sm outline-none ring-primary focus:ring-1" />
            </label>
          </div>
        </header>

        {runOpen && <div className="mb-4 rounded-[28px] bg-card p-4"><p className="mb-2 text-sm text-muted-foreground">Pull fresh SportyBet books for the next 7 days and re-run the models. Leave leagues empty for every fixture.</p><RunButton /></div>}

        {view === "fixtures" && openId && (
          loading || !detail
            ? <div className="grid place-items-center py-24 text-muted-foreground">{loading ? <Loader2 className="size-6 animate-spin" /> : "Fixture not found."}</div>
            : <MatchDetail e={detail} onBack={() => { setOpenId(null); setDetail(null); }} onPick={p => setSlip({ e: detail, p })} />
        )}

        {view === "fixtures" && !openId && (
          <div className="grid gap-6">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div className="flex items-center gap-3">
                {activeLeague && <LeagueFlag flag={activeLeague.flag} kind={activeLeague.kind} />}
                <h1 className="text-2xl font-semibold">{activeLeague ? activeLeague.name : sport === "football" ? "Football" : "Basketball"}</h1>
                <span className="text-sm text-muted-foreground">{activeLeague?.country ?? `${board.total} fixtures · ${date || "next 7 days"}`}</span>
              </div>
              <input aria-label="Search teams" placeholder="Search team" value={q} onChange={e => setQ(e.target.value)} className="h-9 w-full rounded-full bg-card px-4 text-sm outline-none sm:hidden" />
            </div>

            {!league && board.featured && <Hero e={board.featured} onOpen={() => open(board.featured!)} />}
            <TopPicks events={board.events} />

            {[...groups.entries()].map(([l, evs]) => {
              const m = leagueMeta.get(l);
              return (
                <section key={l} className="grid gap-3">
                  <header className="flex items-center gap-2.5 px-1">
                    <LeagueFlag flag={m?.flag} kind={m?.kind} />
                    <button className="truncate text-left text-lg font-semibold hover:underline" onClick={() => go({ league: l })}>{m?.name ?? l}</button>
                    <span className="text-xs text-muted-foreground">{m?.country}</span>
                    <span className="ml-auto font-num text-xs text-muted-foreground">{evs.length}</span>
                  </header>
                  <div className="grid gap-3 md:grid-cols-2">{evs.map(e => <MatchCard key={e.event_id} e={e} onOpen={() => open(e)} />)}</div>
                </section>
              );
            })}
            {!board.events.length && <p className="text-muted-foreground">No fixtures match.</p>}
            {board.total > board.events.length && <p className="text-center text-sm text-muted-foreground">Showing the first {board.events.length} of {board.total}. Pick a day or league in the sidebar to narrow it down.</p>}
          </div>
        )}

        {view === "bets" && <BetsView bets={bets} perf={perf} onDelete={del} onSettle={settle} settling={settling} />}
        {view === "insights" && <Insights events={props.sentiment} social={meta.social} />}

        <p className="mt-10 max-w-3xl text-xs text-muted-foreground">18+. Probabilities, not certainties. Odds are SportyBet&apos;s prices at snapshot time and move; &quot;fair&quot; is the model&apos;s own price where SportyBet doesn&apos;t quote a market.</p>
      </div>

      {slip && (
        <div className="fixed inset-x-0 bottom-6 z-30 mx-auto w-[min(32rem,calc(100%-2rem))] rounded-[28px] bg-card p-4 shadow-2xl ring-1 ring-border lg:left-72">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="text-xs text-muted-foreground">{slip.e.home} v {slip.e.away}</div>
              <div className="font-semibold">{slip.p.label}</div>
              <div className="text-xs text-muted-foreground">{slip.p.odds ? `Odds ${slip.p.odds.toFixed(2)}` : "Not quoted by SportyBet"} · model {pct(slip.p.p)}</div>
            </div>
            <button aria-label="Close slip" onClick={() => setSlip(null)} className="grid size-8 place-items-center rounded-full bg-secondary"><X className="size-4" /></button>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <label htmlFor="stake" className="text-xs text-muted-foreground">Stake (TSh)</label>
            <input id="stake" inputMode="numeric" value={stake} onChange={e => setStake(e.target.value.replace(/[^\d]/g, ""))} className="h-10 w-32 rounded-full bg-secondary px-4 font-num" />
            <span className="ml-auto text-right text-xs text-muted-foreground">Returns<br /><b className="font-num text-sm text-hi">{slip.p.odds ? tsh(Number(stake || 0) * slip.p.odds) : "–"}</b></span>
          </div>
          <Button className="mt-3 w-full" onClick={placeBet} disabled={!Number(stake) || !slip.p.odds}>{slip.p.odds ? "Add to My Bets" : "Only quoted selections can be tracked"}</Button>
        </div>
      )}
      {toast && <div role="status" className="fixed inset-x-0 top-4 z-50 mx-auto w-fit rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">{toast}</div>}
    </div>
  );
}

function Hero({ e, onOpen }: { e: EventPrediction; onOpen: () => void }) {
  const ps = predictedScore(e);
  const call = (e.picks.calls.result ?? e.picks.calls.winner) as Pick | null;
  return (
    <button onClick={onOpen} className="relative overflow-hidden rounded-[28px] bg-primary p-5 text-left text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <div className="pointer-events-none absolute -right-10 -top-10 size-56 rounded-full bg-black/10" />
      <div className="pointer-events-none absolute -bottom-16 right-16 size-40 rounded-full bg-white/20" />
      <div className="relative grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="min-w-0">
          <div className="text-xs font-bold uppercase tracking-widest opacity-70">Featured · {e.league.split(" | ").pop()}</div>
          <div className="mt-1 font-display text-3xl font-bold uppercase leading-none sm:text-4xl">{e.home}<br /><span className="opacity-60">vs</span> {e.away}</div>
          <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-black py-1 pl-1 pr-3 text-xs font-semibold text-white">
            <TeamCrest name={e.home} icon={e.home_icon} size={22} /> {fmtKick(e.kickoff)} EAT <TeamCrest name={e.away} icon={e.away_icon} size={22} />
          </div>
        </div>
        <div className="rounded-3xl bg-black/85 p-4 text-white">
          <div className="text-xs text-zinc-400">Predicted score</div>
          <div className="font-num text-4xl font-bold text-primary">{ps?.score ?? "–"}</div>
          {call && <div className="text-xs text-zinc-300">{call.desc} @ {call.odds?.toFixed(2) ?? "–"} · {pct(call.p)}</div>}
        </div>
      </div>
    </button>
  );
}

function TopPicks({ events }: { events: EventPrediction[] }) {
  const legs = events.flatMap(e => e.picks.safest.slice(0, 1).filter(Boolean).map(p => ({ ...p, match: `${e.home} v ${e.away}` }))).sort((a, b) => b.p - a.p).slice(0, 5);
  const value = events.flatMap(e => e.picks.value.filter(Boolean).map(p => ({ ...p, match: `${e.home} v ${e.away}` }))).sort((a, b) => (b.ev ?? 0) - (a.ev ?? 0)).slice(0, 5);
  const acca = legs.filter(l => l.p >= 0.72 && l.odds);
  const Row = ({ l, ev }: { l: Pick & { match: string }; ev?: boolean }) => (
    <div className="flex items-center gap-3 text-sm">
      <div className="min-w-0 flex-1"><div className="truncate text-xs text-muted-foreground">{l.match}</div><div className="truncate font-semibold">{l.label}</div></div>
      <span className="font-num text-muted-foreground">{ev ? `EV ${((l.ev ?? 0) * 100).toFixed(1)}%` : pct(l.p)}</span><span className="w-12 text-right font-num font-bold text-hi">{l.odds?.toFixed(2) ?? "–"}</span>
    </div>
  );
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-[28px] bg-card p-4"><h3 className="mb-2 text-base font-semibold">Strongest picks</h3><div className="grid gap-2">{legs.map((l, i) => <Row key={i} l={l} />)}</div></div>
      <div className="rounded-[28px] bg-card p-4"><h3 className="mb-2 text-base font-semibold">Value picks</h3><div className="grid gap-2">{value.length ? value.map((l, i) => <Row key={i} l={l} ev />) : <p className="text-sm text-muted-foreground">No positive-value prices in this view.</p>}</div></div>
      <div className="rounded-[28px] bg-card p-4">
        <h3 className="mb-2 text-base font-semibold">Safe accumulator</h3>
        {acca.length >= 2 ? <><div className="font-num text-3xl font-bold text-hi">{acca.reduce((s, l) => s * (l.odds ?? 1), 1).toFixed(2)}</div><div className="text-xs text-muted-foreground">{acca.length} legs · {pct(acca.reduce((s, l) => s * l.p, 1))} to land</div></>
          : <p className="text-sm text-muted-foreground">Not enough strong legs in this view.</p>}
      </div>
    </div>
  );
}
