"""Render a predictions JSON into the standalone HTML report (+ icon sprites in reports/assets/)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import PREDICTIONS, REPORTS

TEMPLATE = Path(__file__).parent / "templates" / "report.html"
ASSETS = REPORTS / "assets"

# Market ids grouped into families for the report's market browser.
FAMILY = {
    "Result": {"1", "10", "11", "12", "13", "15", "60", "63", "64", "83", "85", "86", "47", "219", "290"},
    "Goals / Points": {"18", "19", "20", "21", "23", "24", "25", "26", "27", "28", "68", "69", "70", "71", "74",
                       "90", "91", "92", "93", "548", "549", "550", "552", "553", "225", "227", "228"},
    "Both teams / clean sheets": {"29", "30", "31", "32", "33", "34", "75", "95", "55", "56", "57"},
    "Handicaps": {"14", "16", "66", "88", "223"},
    "Correct score": {"45", "81", "98"},
    "Halves": {"48", "49", "50", "51", "52", "58", "59", "900984"},
    "Combos": {"35", "36", "37", "546", "547"},
    "Corners": {"166", "177", "900300", "900301", "900302", "900303", "162", "165", "173", "176"},
    "Cards": {"139", "152", "900304", "900305", "900306", "900307", "136", "149", "900312"},
    "Shots & fouls": {"900394", "900393", "900552", "900553", "900546", "900547", "900342", "900544", "900545",
                      "900396", "900568", "900569", "900320", "900318", "900539", "900570"},
}
FAMILIES = list(FAMILY) + ["Other"]


def _family(mid: str) -> int:
    for i, (k, ids) in enumerate(FAMILY.items()):
        if mid in ids:
            return i
    return len(FAMILY)


def slim(pred: dict, icons: dict | None) -> dict:
    crest_ix = (icons or {}).get("crests", {}).get("index", {})
    flag_ix = (icons or {}).get("flags", {}).get("index", {})
    names: dict[str, int] = {}
    out = {k: pred.get(k) for k in ("generated", "day", "timezone", "source", "window_hours", "social")}
    out["families"] = FAMILIES
    out["sports"] = {}
    for sport, S in pred["sports"].items():
        evs = []
        for e in S["events"]:
            mk = []
            for r in sorted(e["markets"], key=lambda r: -r["p"]):
                ni = names.setdefault(r["market"], len(names))
                mk.append([ni, r["desc"], r["odds"], round(r["p"], 3), r["fair"] and round(r["fair"], 3),
                           r["ev"] if r["ev"] is None else round(r["ev"], 3), _family(r["mid"]), r.get("push", 0), r["mid"]])
            keep = {k: e.get(k) for k in ("event_id", "game_id", "league", "kickoff", "home", "away", "venue", "coverage",
                                          "model", "research", "consensus", "picks", "depth", "league_kind")}
            keep["model"] = {k: v for k, v in (e.get("model") or {}).items() if k not in ("fit_error", "rho", "count_priors")}
            keep["ch"] = crest_ix.get(e.get("home_id"))
            keep["ca"] = crest_ix.get(e.get("away_id"))
            keep["fi"] = flag_ix.get(e.get("flag"))
            keep["markets"] = mk
            evs.append(keep)
        out["sports"][sport] = {"events": evs, "accumulators": S["accumulators"], "fixtures_scanned": S["fixtures_scanned"]}
    out["market_names"] = [n for n, _ in sorted(names.items(), key=lambda kv: kv[1])]
    if icons:
        out["sprites"] = {k: {kk: icons[k][kk] for kk in ("cols", "w", "h", "file")} for k in ("crests", "flags")}
    return out


def render(day: str, out: Path) -> Path:
    pred = json.loads((PREDICTIONS / f"{day}.json").read_text(encoding="utf-8"))
    icons_meta = ASSETS / "icons.json"
    icons = json.loads(icons_meta.read_text(encoding="utf-8")) if icons_meta.exists() else None
    data = json.dumps(slim(pred, icons), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data)
    out.parent.mkdir(parents=True, exist_ok=True)
    if icons and out.parent.resolve() != REPORTS.resolve():
        shutil.copytree(ASSETS, out.parent / "assets", dirs_exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
