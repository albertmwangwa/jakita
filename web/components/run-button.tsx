"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function RunButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [leagues, setLeagues] = useState("");
  const [research, setResearch] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function go() {
    setBusy(true);
    setMsg(null);
    const res = await fetch("/api/run", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ leagues, research }) });
    const j = await res.json();
    setBusy(false);
    if (j.ok) { setMsg(`Updated ${j.day}`); router.push(`/?day=${j.day}`); router.refresh(); }
    else setMsg(j.error?.slice(0, 300) ?? "Run failed");
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input id="leagues" value={leagues} onChange={e => setLeagues(e.target.value)} placeholder="Leagues, e.g. Premier League, NBA"
        className="h-10 w-64 max-w-full rounded-full bg-secondary px-4 text-sm outline-none ring-primary focus:ring-1" />
      <label className="flex items-center gap-1 text-xs text-muted-foreground">
        <input id="research" type="checkbox" checked={research} onChange={e => setResearch(e.target.checked)} /> Research
      </label>
      <Button onClick={go} disabled={busy}>{busy ? <Loader2 className="animate-spin" /> : <Play />}{busy ? "Running…" : "Run predictions"}</Button>
      {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
    </div>
  );
}
