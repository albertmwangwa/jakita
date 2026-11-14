"""End-to-end: fixtures -> full books -> models -> priced markets -> picks -> JSON."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from . import consensus, icons, tracker
from .config import EAT, EXCLUDED_GROUPS, MIN_ODDS, PREDICTIONS, RESEARCH, TOP_LEAGUES
from .markets import Market, index, parse_markets
from .models import basketball as bb
from .models import counts as cnt
from .models import football as fb
from .sources.sportybet import SportyBet, kickoff, league_of, select

def _ou(lines):
    return [f"{s} {l}" for l in lines for s in ("Over", "Under")]


# Markets priced by the goal model even when SportyBet doesn't quote them (list-only fixtures).
FOOTBALL_CATALOGUE = (
    [("10", "Double Chance", "", ["Home or Draw", "Home or Away", "Draw or Away"]),
     ("11", "Draw No Bet", "", ["Home", "Away"]),
     ("29", "GG/NG", "", ["Yes", "No"]),
     ("60", "1st Half - 1X2", "", ["Home", "Draw", "Away"]),
     ("75", "1st Half - GG/NG", "", ["Yes", "No"]),
     ("47", "Halftime/Fulltime", "", [f"{a}/{b}" for a in ("Home", "Draw", "Away") for b in ("Home", "Draw", "Away")]),
     ("45", "Correct Score", "", [f"{h}:{a}" for h in range(5) for a in range(5)]),
     ("21", "Exact Goals", "variant=sr:exact_goals:6+", ["0", "1", "2", "3", "4", "5", "6+"]),
     ("548", "Multigoals", "", ["1-2", "1-3", "2-3", "2-4", "3-4", "3-5", "4-6"]),
     ("15", "Winning Margin", "variant=sr:winning_margin:3+", ["Home by 1", "Home by 2", "Home by 3+", "Draw", "Away by 1", "Away by 2", "Away by 3+"]),
     ("26", "Odd/Even", "", ["Odd", "Even"]),
     ("31", "Home Team Clean Sheet", "", ["Yes", "No"]),
     ("32", "Away Team Clean Sheet", "", ["Yes", "No"]),
     ("33", "Home Team Win To Nil", "", ["Yes", "No"]),
     ("34", "Away Team Win To Nil", "", ["Yes", "No"]),
     ("52", "Highest Scoring Half", "", ["1st half", "2nd half", "equal"]),
     ("35", "1X2 & GG/NG", "", [f"{r} & {b}" for r in ("Home", "Draw", "Away") for b in ("Yes", "No")]),
     ("37", "1X2 & Over/Under", "total=2.5", [f"{r} & {s} 2.5" for r in ("Home", "Draw", "Away") for s in ("Over", "Under")])]
    + [("18", "Over/Under", f"total={l}", _ou([l])) for l in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)]
    + [("19", "Home O/U", f"total={l}", _ou([l])) for l in (0.5, 1.5, 2.5)]
    + [("20", "Away O/U", f"total={l}", _ou([l])) for l in (0.5, 1.5, 2.5)]
    + [("68", "1st Half - Over/Under", f"total={l}", _ou([l])) for l in (0.5, 1.5, 2.5)]
)

TIPSTER_WEIGHT_PER_SOURCE = 0.12
TIPSTER_WEIGHT_CAP = 0.35

# Market families used for "safest" picks and per-family calls.
CORE_FOOTBALL = {"1", "10", "11", "18", "19", "20", "29", "60", "63", "68", "16", "14", "166", "139",
                 "900300", "900301", "548", "547", "37"}
CORE_BASKET = {"219", "223", "225", "227", "228", "68", "66"}


def _research(day: str) -> dict:
    p = RESEARCH / f"{day}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _fair(by_id, mid, desc, spec=None):
    for m in by_id.get(mid, []):
        if spec is None or (m.spec or "") == spec:
            for o in m.outcomes:
                if o.desc == desc:
                    return o.fair
    return None


def _blend(book: float | None, cons: float | None, n: int) -> float | None:
    if book is None or cons is None:
        return book
    w = min(TIPSTER_WEIGHT_CAP, TIPSTER_WEIGHT_PER_SOURCE * n)
    return (1 - w) * book + w * cons


def price_event(e: dict, sport: str, notes: dict) -> dict:
    markets = parse_markets(e)
    by_id = index(markets)
    tipsters = notes.get("tipsters", [])
    agg = consensus.aggregate(tipsters)
    model_summary: dict = {}
    pricer = None
    counts: dict[str, cnt.CountModel] = {}

    if sport == "football":
        overrides: dict = {}
        c1 = consensus.one_x_two_consensus(tipsters)
        if c1:
            book = [_fair(by_id, "1", d) for d in ("Home", "Draw", "Away")]
            if None not in book:
                w = min(TIPSTER_WEIGHT_CAP, TIPSTER_WEIGHT_PER_SOURCE * c1[1])
                overrides["1x2"] = [(1 - w) * b + w * c for b, c in zip(book, c1[0])]
        for g in agg:
            if g["avg_prob"] is None:
                continue
            n = sum(1 for _ in g["sources"])
            if g["market_id"] == "18" and g["spec"] == "total=2.5":
                p_over = g["avg_prob"] if g["desc"].startswith("Over") else 1 - g["avg_prob"]
                overrides["o25"] = _blend(_fair(by_id, "18", "Over 2.5", "total=2.5"), p_over, n)
            if g["market_id"] == "29":
                p_yes = g["avg_prob"] if g["desc"] == "Yes" else 1 - g["avg_prob"]
                overrides["btts"] = _blend(_fair(by_id, "29", "Yes"), p_yes, n)
        overrides = {k: v for k, v in overrides.items() if v is not None}
        gm = fb.fit(by_id, overrides)
        priors = {}
        for t in tipsters:
            if t.get("avg") and t["market"].lower().startswith("corners"):
                priors["corners"] = t["avg"]
            if t.get("avg") and t["market"].lower().startswith("cards"):
                priors["bookings"] = t["avg"]
        counts = cnt.fit_all(by_id, priors)
        if gm:
            xh, xa = gm.xg
            model_summary = {"xg_home": round(xh, 2), "xg_away": round(xa, 2), "rho": round(gm.rho, 3),
                             "first_half_share": gm.share1, "fit_error": round(gm.fit_error, 5),
                             "blended": sorted(overrides), "top_scores": [(s, round(p, 4)) for s, p in gm.top_scores(6)],
                             "counts": {k: v.summary() for k, v in counts.items()}, "count_priors": priors}

        def pricer(m: Market, desc: str):
            fam = cnt.family_of(m.id)
            if fam and fam in counts:
                return counts[fam].price(m, desc)
            return fb.price(gm, m, desc) if gm else None
    else:
        nba = "NBA" in league_of(e)
        bm = bb.fit(by_id, nba, e["homeTeamName"])
        if bm:
            model_summary = bm.summary()
            pricer = bm.price

    rows = []
    book_keys = {(m.id, m.spec or "") for m in markets}
    if sport == "football" and pricer and model_summary:
        # Model-only prices for markets this book doesn't quote (all of them for list-only fixtures).
        for mid, name, spec, descs in FOOTBALL_CATALOGUE:
            if (mid, spec) in book_keys:
                continue
            m = Market(mid, name, spec or None, "Model", [])
            for d in descs:
                res = pricer(m, d)
                if res is None:
                    continue
                pw, pp = res
                rows.append({"mid": mid, "market": name, "spec": spec, "group": "Model", "desc": d, "odds": None,
                             "fair": None, "p": round(pw, 4), "push": round(pp, 4), "ev": None, "modeled": True, "margin": 0.0})
    for m in markets:
        if m.group in EXCLUDED_GROUPS:
            continue
        for o in m.outcomes:
            res = pricer(m, o.desc) if pricer else None
            modeled = res is not None and not any(map(math.isnan, res))
            pw, pp = res if modeled else (o.fair, 0.0)
            pw = max(0.0, min(1.0, pw))
            if modeled and pp < 1e-9:
                pw = tracker.calibrate(m.id, pw)  # no-op until enough settled results exist
            ev = pw * o.odds + pp - 1
            rows.append({"mid": m.id, "market": m.name, "spec": m.spec or "", "group": m.group or "",
                         "desc": o.desc, "odds": o.odds, "fair": round(o.fair, 4), "p": round(pw, 4),
                         "push": round(pp, 4), "ev": round(ev, 4), "modeled": modeled,
                         "margin": round(m.margin, 4)})

    picks = make_picks(rows, sport, model_summary)
    return {
        "event_id": e["eventId"], "game_id": e.get("gameId"), "sport": sport, "league": league_of(e),
        "kickoff": kickoff(e).isoformat(), "home": e["homeTeamName"], "away": e["awayTeamName"],
        "venue": (e.get("fixtureVenue") or {}).get("name"),
        "home_id": e.get("homeTeamId"), "away_id": e.get("awayTeamId"),
        "home_icon": icons.crest_url(e.get("homeTeamId")) or e.get("homeTeamIcon"),
        "away_icon": icons.crest_url(e.get("awayTeamId")) or e.get("awayTeamIcon"),
        "flag": icons.flag_code(league_of(e)), "league_kind": icons.league_kind(league_of(e)),
        "depth": "full" if len(markets) > 40 else "model",
        "coverage": {"markets": len(markets), "outcomes": len(rows), "modeled": sum(r["modeled"] for r in rows)},
        "model": model_summary, "research": {k: v for k, v in notes.items() if k != "tipsters"},
        "consensus": agg, "tipsters": tipsters, "picks": picks,
        "markets": [r for r in rows if r["modeled"]],
    }


def _label(r: dict) -> str:
    return f"{r['market']}: {r['desc']}"


def _best(rows, mid, spec=None):
    c = [r for r in rows if r["mid"] == mid and (spec is None or r["spec"] == spec)]
    return max(c, key=lambda r: r["p"]) if c else None


def _main_line(rows, mid):
    """Pick the line whose two sides are closest to 50/50 and return the likelier side.

    Half lines (x.5, no push) are preferred when the market offers them."""
    by_spec: dict[str, list] = {}
    for r in rows:
        if r["mid"] == mid:
            by_spec.setdefault(r["spec"], []).append(r)
    half = {s: v for s, v in by_spec.items() if s.endswith(".5")}
    by_spec = half or by_spec
    if not by_spec:
        return None
    spec = min(by_spec, key=lambda s: abs(max(x["p"] for x in by_spec[s]) - 0.5))
    return max(by_spec[spec], key=lambda r: r["p"])


def _pushable(spec: str) -> bool:
    """True for whole/quarter goal or point lines (total=2, hcp=-1, total=2.25...)."""
    for part in spec.split("|"):
        k, _, v = part.partition("=")
        if k in ("total", "hcp"):
            try:
                return not (float(v) * 2).is_integer() or float(v).is_integer()
            except ValueError:
                return False
    return False


def _safest_line(rows, mid, floor=0.72, min_odds=1.25):
    c = [r for r in rows if r["mid"] == mid and r["p"] >= floor and r["odds"] >= min_odds and not _pushable(r["spec"])]
    return min(c, key=lambda r: r["p"]) if c else None


def _pick(r: dict | None, why: str = "") -> dict | None:
    if not r:
        return None
    conf = "High" if r["p"] >= 0.75 else "Medium" if r["p"] >= 0.6 else "Low"
    return {"label": _label(r), "mid": r["mid"], "spec": r["spec"], "desc": r["desc"], "odds": r["odds"],
            "p": r["p"], "ev": r["ev"], "confidence": conf, "why": why}


def make_picks(rows: list[dict], sport: str, model: dict) -> dict:
    modeled = [r for r in rows if r["modeled"] and r["odds"] and r["odds"] >= MIN_ODDS]
    model_only = [r for r in rows if r["modeled"]]
    core = CORE_FOOTBALL if sport == "football" else CORE_BASKET
    calls: dict[str, dict | None] = {}
    if sport == "football":
        calls["result"] = _pick(_best(modeled, "1"), "1X2, most likely outcome")
        calls["double_chance"] = _pick(_best(modeled, "10") or _best(model_only, "10"))
        calls["goals_main"] = _pick(_main_line(modeled, "18"), "Main goals line")
        calls["goals_safe"] = _pick(_safest_line(modeled, "18"), "Safest goals line at 1.25+")
        calls["btts"] = _pick(_best(modeled, "29") or _best(model_only, "29"))
        calls["first_half"] = _pick(_best(modeled, "60") or _best(model_only, "60"))
        calls["ht_ft"] = _pick(_best(modeled, "47") or _best(model_only, "47"))
        calls["corners"] = _pick(_main_line(modeled, "166"), "Main corners line")
        calls["corners_safe"] = _pick(_safest_line(modeled, "166"))
        calls["bookings"] = _pick(_main_line(modeled, "139"), "Main bookings line")
        calls["shots_on_target"] = _pick(_main_line(modeled, "900393"))
        cs = sorted([r for r in rows if r["mid"] == "45" and r["modeled"]], key=lambda r: -r["p"])[:3]
        calls["correct_score"] = [_pick(r) for r in cs]
    else:
        calls["winner"] = _pick(_best(modeled, "219"), "Moneyline incl. OT")
        calls["spread"] = _pick(_main_line(modeled, "223"), "Main handicap")
        calls["total"] = _pick(_main_line(modeled, "225"), "Main total")
        calls["total_safe"] = _pick(_safest_line(modeled, "225"))
        calls["home_total"] = _pick(_main_line(modeled, "227"))
        calls["away_total"] = _pick(_main_line(modeled, "228"))
        calls["first_half_total"] = _pick(_main_line(modeled, "68"))
        calls["first_half_spread"] = _pick(_main_line(modeled, "66"))

    safe_pool = [r for r in modeled if r["mid"] in core and r["odds"] >= 1.25 and not _pushable(r["spec"])]
    safest = sorted(safe_pool, key=lambda r: -r["p"])[:3]
    value_pool = [r for r in modeled if r["ev"] is not None and r["ev"] >= 0.02 and r["p"] >= 0.33 and r["mid"] not in LOW_TRUST_VALUE]
    value = sorted(value_pool, key=lambda r: -r["ev"])[:5]
    return {"calls": calls, "safest": [_pick(r) for r in safest],
            "value": [_pick(r, _value_reason(r, model)) for r in value]}


# Count-stat 1X2 / handicap markets depend on the between-team correlation the independent
# model ignores; offsides/shots/fouls ladders are thin. Shown as calls, never as value.
LOW_TRUST_VALUE = {"162", "165", "173", "176", "136", "900312", "149", "900320", "900318", "900539",
                   "900570", "900396", "900568", "900569", "900342", "900544", "900545", "900394",
                   "900552", "900553", "900393", "900546", "900547"}


def _value_reason(r: dict, model: dict) -> str:
    fam = {"166": "corners", "900300": "corners", "900301": "corners", "139": "bookings"}.get(r["mid"])
    counts = model.get("counts", {}) if model else {}
    if fam and model.get("count_priors", {}).get(fam):
        return (f"Stats-site average ({model['count_priors'][fam]}) blended with the book's ladder "
                f"gives {counts.get(fam, {}).get('total_mean')} expected; odds imply more.")
    if model.get("blended"):
        return "Tipster/stat-model consensus (" + ", ".join(model["blended"]) + ") moves the fair price past the odds."
    return "Priced longer than SportyBet's own main markets imply (cross-market inconsistency)."


def accumulators(events: list[dict]) -> dict:
    legs = []
    headline = {"1", "10", "11", "18", "29", "166", "219", "223", "225"}
    for ev in events:
        s = next((x for x in ev["picks"].get("safest", []) if x and x["mid"] in headline), None)
        if s and s["p"] >= 0.72:
            legs.append({**s, "match": f"{ev['home']} v {ev['away']}", "kickoff": ev["kickoff"]})
    legs = sorted(legs, key=lambda l: -l["p"])[:5]
    val = []
    for ev in events:
        v = (ev["picks"].get("value") or [None])[0]
        if v and v["p"] >= 0.45:
            val.append({**v, "match": f"{ev['home']} v {ev['away']}", "kickoff": ev["kickoff"]})
    val = sorted(val, key=lambda l: -l["ev"])[:4]

    def combo(ls):
        if not ls:
            return None
        return {"legs": ls, "odds": round(math.prod(l["odds"] for l in ls), 2), "p": round(math.prod(l["p"] for l in ls), 4)}

    return {"safe": combo(legs), "value": combo(val)}


def run(client: SportyBet, day: str, sports: list[str], leagues: list[str] | None = None,
        days: list[dt.date] | None = None, teams: list[str] | None = None, max_full: int = 40,
        pages: int = 20, hours: int = 168) -> dict:
    """Every fixture in the window is predicted. The top `max_full` (top leagues first) also get
    their full market book fetched; the rest are modelled from the list feed's main markets."""
    notes_all = _research(day)
    out = {"generated": dt.datetime.now(EAT).isoformat(timespec="minutes"), "day": day, "window_hours": hours,
           "timezone": "EAT (UTC+3)", "source": "SportyBet TZ", "sports": {}}
    for sport in sports:
        fixtures = client.fixtures(sport, max_pages=pages, hours=hours)
        seen, uniq = set(), []
        for f in fixtures:
            if f["eventId"] not in seen:
                seen.add(f["eventId"]); uniq.append(f)
        chosen = select(uniq, leagues, days, teams)
        top = TOP_LEAGUES[sport]
        headline = {f["eventId"] for f in select(chosen, top, None)[:max_full]}
        events = []
        for f in chosen:
            full = client.event(f["eventId"]) if f["eventId"] in headline else None
            notes = notes_all.get(f["eventId"].split(":")[-1], {})
            try:
                events.append(price_event(full or f, sport, notes))
            except Exception as exc:  # one bad book must not sink the run
                print(f"skip {f['eventId']}: {exc}")
        out["sports"][sport] = {"events": events, "accumulators": accumulators(events),
                                "fixtures_scanned": len(uniq)}
    out["social"] = notes_all.get("_social")
    out["notes"] = {k: v for k, v in notes_all.items() if k.startswith("_") and k not in ("_social", "_meta")}
    return out


def save(pred: dict, day: str) -> Path:
    PREDICTIONS.mkdir(parents=True, exist_ok=True)
    p = PREDICTIONS / f"{day}.json"
    for S in pred["sports"].values():
        for e in S["events"]:
            for r in e["markets"]:
                for k in ("group", "margin", "modeled"):
                    r.pop(k, None)
                if not r["push"]:
                    r.pop("push")
    p.write_text(json.dumps(pred, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p
