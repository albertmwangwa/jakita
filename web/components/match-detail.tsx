"use client";

import { useState } from "react";
import { ChevronLeft, Plus } from "lucide-react";
import type { EventPrediction, Pick } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn, ev, pct } from "@/lib/utils";
import { MatchCard } from "./match-card";

const CALL_LABELS: Record<string, string> = {
  result: "Result", double_chance: "Double chance", goals_main: "Goals (main)", goals_safe: "Goals (safe)", btts: "Both teams score",
  first_half: "1st half", ht_ft: "HT / FT", corners: "Corners", corners_safe: "Corners (safe)", bookings: "Bookings",
  shots_on_target: "Shots on target", winner: "Winner", spread: "Handicap", total: "Total", total_safe: "Total (safe)",
  home_total: "Home points", away_total: "Away points", first_half_total: "1st half total", first_half_spread: "1st half handicap",
};

/* Dark tiles as in the mock's "Performance" block: label, small grey reference, lime model value. */
function perfTiles(e: EventPrediction): { k: string; ref: string; v: string }[] {
  const m = e.model ?? {};
  if (e.sport === "football") {
    const c = m.counts ?? {};
    const t: { k: string; ref: string; v: string }[] = [
      { k: "Exp. goals", ref: e.home.slice(0, 3).toUpperCase(), v: m.xg_home?.toFixed(2) ?? "–" },
      { k: "Exp. goals", ref: e.away.slice(0, 3).toUpperCase(), v: m.xg_away?.toFixed(2) ?? "–" },
      { k: "1st half share", ref: "goals", v: m.first_half_share != null ? pct(m.first_half_share) : "–" },
    ];
    const add = (k: string, key: string) => c[key]?.total_mean != null && t.push({ k, ref: c[key].home_mean != null ? `${c[key].home_mean}–${c[key].away_mean}` : "total", v: String(c[key].total_mean) });
    add("Corner kicks", "corners"); add("Bookings", "bookings"); add("Shots on goal", "shots_on_target"); add("Shots", "shots"); add("Fouls", "fouls"); add("Offsides", "offsides");
    return t;
  }
  return [
    { k: "Exp. points", ref: e.home.split(" ").pop()!.slice(0, 3).toUpperCase(), v: String(m.exp_home ?? "–") },
    { k: "Exp. points", ref: e.away.split(" ").pop()!.slice(0, 3).toUpperCase(), v: String(m.exp_away ?? "–") },
    { k: "Margin", ref: `±${m.margin_sd}`, v: `${m.exp_margin > 0 ? "+" : ""}${m.exp_margin}` },
    { k: "Total", ref: `±${m.total_sd}`, v: String(m.exp_total ?? "–") },
  ];
}

export function MatchDetail({ e, onBack, onPick }: { e: EventPrediction; onBack: () => void; onPick: (p: Pick) => void }) {
  const [selected, setSelected] = useState<Pick | null>(e.picks.safest[0] ?? null);
  const [fam, setFam] = useState("");
  const calls = Object.entries(e.picks.calls).filter(([, c]) => c && !Array.isArray(c)) as [string, Pick][];
  const cs = (e.picks.calls.correct_score as Pick[] | undefined) ?? [];
  const r = e.research ?? {};
  const markets = e.markets.filter(m => !fam || m.market === fam).sort((a, b) => b.p - a.p).slice(0, 300);

  const PickRow = ({ p, k }: { p: Pick; k?: string }) => (
    <button onClick={() => setSelected(p)} className={cn("flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-secondary", selected?.label === p.label && "bg-secondary ring-1 ring-primary")}>
      <div className="min-w-0 flex-1">
        {k && <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{CALL_LABELS[k] ?? k}</div>}
        <div className="truncate font-semibold">{k ? p.desc : p.label}</div>
      </div>
      {(p.ev ?? 0) > 0 && <Badge variant="Value">Value</Badge>}
      <Badge variant={p.confidence}>{pct(p.p)}</Badge>
      <span className="w-12 text-right font-num font-semibold">{p.odds?.toFixed(2) ?? "fair " + (1 / p.p).toFixed(2)}</span>
    </button>
  );

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={onBack}><ChevronLeft /> Back</Button>
        <span className="text-xs text-muted-foreground">{e.coverage.markets} markets · {e.coverage.modeled} prices modelled</span>
      </div>

      <MatchCard e={e} onOpen={() => undefined} />

      <section className="rounded-[28px] bg-card p-3">
        <h3 className="px-2 pb-1 pt-1 text-lg font-semibold">Calls</h3>
        <div className="grid gap-0.5">{calls.map(([k, p]) => <PickRow key={k} p={p} k={k} />)}</div>
        {cs.length > 0 && <p className="px-3 pt-2 text-sm text-muted-foreground">Correct score: {cs.map(x => `${x.desc} (${x.odds?.toFixed(2) ?? "fair"})`).join(" · ")}</p>}
        <div className="mt-3 flex items-center gap-2 px-1">
          <div className="min-w-0 flex-1 truncate text-sm">{selected ? <><span className="text-muted-foreground">Selected:</span> <b>{selected.label}</b> @ {selected.odds?.toFixed(2) ?? "fair " + (1 / selected.p).toFixed(2)}</> : "Pick a selection"}</div>
          <Button variant="ink" className="min-w-36" disabled={!selected} onClick={() => selected && onPick(selected)}>Make Bet</Button>
        </div>
      </section>

      <section className="rounded-[28px] bg-card p-4">
        <h3 className="mb-3 text-lg font-semibold">Performance</h3>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl bg-border sm:grid-cols-3">
          {perfTiles(e).map((t, i) => (
            <div key={i} className="bg-card p-3">
              <div className="text-xs text-muted-foreground">{t.k}</div>
              <div className="mt-1 flex items-baseline justify-between gap-2">
                <span className="text-xs text-muted-foreground">{t.ref}</span>
                <span className="font-num text-xl font-bold text-hi">{t.v}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-[28px] bg-card p-3">
          <h3 className="px-2 pb-1 text-base font-semibold">Strongest picks</h3>
          {e.picks.safest.map((p, i) => <PickRow key={i} p={p} />)}
        </div>
        <div className="rounded-[28px] bg-card p-3">
          <h3 className="px-2 pb-1 text-base font-semibold">Value picks</h3>
          {e.picks.value.length ? e.picks.value.map((p, i) => (
            <div key={i}><PickRow p={p} /><p className="px-3 pb-2 text-xs text-muted-foreground">EV {p.ev == null ? "–" : ev(p.ev)} · {p.why}</p></div>
          )) : <p className="px-3 text-sm text-muted-foreground">No positive-value prices found.</p>}
        </div>
      </section>

      {(r.context || r.absences || r.lineups || r.h2h) && (
        <section className="grid gap-2 rounded-[28px] bg-card p-4 text-sm">
          <h3 className="text-base font-semibold">Team news</h3>
          {r.context && <p>{r.context}</p>}
          {r.form && <p><span className="text-muted-foreground">Form:</span> {r.form.home} · {r.form.away}</p>}
          {r.h2h && <p><span className="text-muted-foreground">H2H:</span> {r.h2h}</p>}
          {r.absences && <p><span className="text-muted-foreground">Out:</span> {e.home}: {(r.absences.home ?? []).join(", ") || "none"} · {e.away}: {(r.absences.away ?? []).join(", ") || "none"}</p>}
          {r.lineups && <p className="text-muted-foreground">XIs: {r.lineups.home} | {r.lineups.away}</p>}
        </section>
      )}

      <section className="rounded-[28px] bg-card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">All markets</h3>
          <select aria-label="Market" className="h-9 rounded-full border bg-secondary px-3 text-sm" value={fam} onChange={x => setFam(x.target.value)}>
            <option value="">All ({e.markets.length})</option>{[...new Set(e.markets.map(m => m.market))].map(n => <option key={n}>{n}</option>)}
          </select>
        </div>
        <div className="max-h-[28rem] overflow-auto rounded-2xl border">
          <Table>
            <TableHeader><TableRow><TableHead>Market</TableHead><TableHead>Selection</TableHead><TableHead className="text-right">Odds</TableHead><TableHead className="text-right">Model</TableHead><TableHead className="text-right">EV</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>
              {markets.map((m, i) => (
                <TableRow key={i}>
                  <TableCell className="whitespace-nowrap">{m.market}</TableCell><TableCell className="whitespace-nowrap">{m.desc}</TableCell>
                  <TableCell className="text-right font-num">{m.odds?.toFixed(2) ?? "–"}</TableCell><TableCell className="text-right font-num">{pct(m.p)}</TableCell>
                  <TableCell className={cn("text-right font-num", (m.ev ?? 0) > 0 && "font-semibold text-good")}>{m.ev == null ? "–" : ev(m.ev)}</TableCell>
                  <TableCell className="text-right">
                    <button aria-label={`Select ${m.market} ${m.desc}`} className="grid size-7 place-items-center rounded-full bg-primary text-primary-foreground"
                      onClick={() => setSelected({ label: `${m.market}: ${m.desc}`, mid: m.mid, spec: m.spec, desc: m.desc, odds: m.odds, p: m.p, ev: m.ev, confidence: m.p >= 0.75 ? "High" : m.p >= 0.6 ? "Medium" : "Low", why: "" })}>
                      <Plus className="size-4" />
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
