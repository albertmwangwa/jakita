import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import { ROOT } from "@/lib/data";

const run = promisify(execFile);

// POST /api/settle {day?, transport?} -> fetch final scores, settle open bets, refresh performance.
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const day = /^\d{4}-\d{2}-\d{2}$/.test(body.day ?? "") ? body.day : new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10);
  const transport = ["http", "firecrawl", "snapshot"].includes(body.transport) ? body.transport : "http";
  try {
    const r = await run(process.env.JAKITA_PYTHON ?? "python", ["-m", "jakita", "results", "--day", day, "--transport", transport],
      { cwd: ROOT, timeout: 10 * 60 * 1000, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
    return NextResponse.json({ ok: true, log: r.stdout });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.stderr || e?.message || e) }, { status: 500 });
  }
}
