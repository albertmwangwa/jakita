import { board, listDays, loadDay, sentiment } from "@/lib/data";
import { AppShell } from "@/components/app-shell";
import { RunButton } from "@/components/run-button";

export const dynamic = "force-dynamic";

type SP = { day?: string; view?: string; sport?: string; league?: string; date?: string; q?: string };

export default async function Page({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const days = await listDays();
  const day = sp.day ?? days[0];
  const data = day ? await loadDay(day) : null;

  if (!data) {
    return (
      <main className="mx-auto grid max-w-xl gap-4 px-4 py-16">
        <h1 className="text-2xl font-bold">JAKITA<span className="text-hi">.</span></h1>
        <p className="text-muted-foreground">No predictions yet. Run the pipeline to build the board.</p>
        <RunButton />
      </main>
    );
  }
  const view = (["fixtures", "bets", "insights"].includes(sp.view ?? "") ? sp.view : "fixtures") as "fixtures" | "bets" | "insights";
  const sport = sp.sport && data.sports[sp.sport] ? sp.sport : Object.keys(data.sports)[0];
  const b = board(data, { sport, league: sp.league, date: sp.date, q: sp.q });
  return (
    <AppShell
      meta={{ generated: data.generated, source: data.source, windowHours: (data as any).window_hours ?? 48, social: data.social?.x_com }}
      days={days} day={day!} view={view} sport={sport} league={sp.league ?? ""} date={sp.date ?? ""} q={sp.q ?? ""}
      board={b} sentiment={view === "insights" ? sentiment(data) : []}
    />
  );
}
