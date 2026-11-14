import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import { ROOT } from "@/lib/data";

const run = promisify(execFile);

// POST /api/run {day?, leagues?, sports?, transport?, research?}
// Runs the Python pipeline on demand: optional research, then predict, then render.
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const day: string = /^\d{4}-\d{2}-\d{2}$/.test(body.day ?? "") ? body.day : new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10);
  const safe = (s: unknown) => String(s ?? "").replace(/[^\w ,|.\-]/g, "");
  const py = process.env.JAKITA_PYTHON ?? "python";
  const common = ["--day", day, "--transport", safe(body.transport) || "http"];
  const opts = { cwd: ROOT, timeout: 15 * 60 * 1000, maxBuffer: 16 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: "utf-8" } };
  try {
    const log: string[] = [];
    if (body.research) {
      const r = await run(py, ["-m", "jakita", "research", ...common, "--leagues", safe(body.leagues)], opts);
      log.push(r.stdout);
    }
    const p = await run(py, ["-m", "jakita", "predict", ...common, "--sports", safe(body.sports) || "football,basketball",
      ...(body.leagues ? ["--leagues", safe(body.leagues)] : [])], opts);
    log.push(p.stdout);
    const r = await run(py, ["-m", "jakita", "render", "--day", day], opts);
    log.push(r.stdout);
    return NextResponse.json({ ok: true, day, log });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.stderr || e?.message || e) }, { status: 500 });
  }
}
