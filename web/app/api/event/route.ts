import { NextResponse } from "next/server";
import { findEvent, loadDay } from "@/lib/data";

// GET /api/event?day=YYYY-MM-DD&id=sr:match:... -> one fixture with every priced market.
export async function GET(req: Request) {
  const u = new URL(req.url);
  const data = await loadDay(u.searchParams.get("day") ?? "");
  const e = data && findEvent(data, u.searchParams.get("id") ?? "");
  return e ? NextResponse.json(e) : NextResponse.json({ error: "Fixture not found" }, { status: 404 });
}
