"""Results, bet slip settlement, and model performance / calibration.

Files under data/:
  results.json      {event_id: {"ft": "2:1", "ht": "1:0" | null, "status": ..., "source": ...}}
  bets.json         [{id, event_id, label, mid, spec, desc, odds, p, stake, status, payout, ...}]
  performance.json  per market family: n, hit rate, Brier, flat-stake ROI, calibration bins
  calibration.json  per family: isotonic map [[p_model, p_observed], ...] used by the pipeline
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import numpy as np

from .config import DATA, EAT, PREDICTIONS
from .markets import Market
from .models import football as fb

RESULTS = DATA / "results.json"
BETS = DATA / "bets.json"
PERF = DATA / "performance.json"
CALIB = DATA / "calibration.json"

# Markets settleable from the full-time score alone, and those that also need half-time.
FT_ONLY = {"1", "10", "11", "12", "13", "14", "15", "16", "18", "19", "20", "21", "23", "24", "25", "26", "27", "28",
           "29", "30", "31", "32", "33", "34", "35", "36", "37", "45", "546", "547", "548", "549", "550"}
NEEDS_HT = {"47", "48", "49", "50", "51", "52", "55", "56", "57", "58", "59", "60", "63", "64", "68", "69", "70",
            "71", "74", "75", "81", "83", "85", "86", "88", "90", "91", "92", "93", "95", "98", "552", "553", "66", "900984"}
BASKET = {"219", "223", "225", "227", "228", "11"}

FAMILIES = {
    "1X2 / DC / DNB": {"1", "10", "11", "12", "13", "219"},
    "Goals O/U": {"18", "19", "20", "68", "69", "70", "90"},
    "BTTS": {"29", "75", "95"},
    "Correct score": {"45", "81", "98"},
    "Handicap": {"14", "16", "66", "88", "223"},
    "Combos": {"35", "36", "37", "546", "547"},
    "Points O/U": {"225", "227", "228"},
}


def family(mid: str) -> str:
    return next((k for k, v in FAMILIES.items() if mid in v), "Other")


def _load(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ results ----

def parse_result(event: dict) -> dict | None:
    """Read a finished SportyBet event. Field names follow SportyBet's live feed
    (setScore "h:a", gameScore list of period scores); returns None if not finished."""
    status = (event.get("matchStatus") or "").lower()
    score = event.get("setScore")
    if not score or not re.match(r"^\d+:\d+$", score) or status not in ("ended", "ft", "aet", "ap", "finished"):
        return None
    periods = event.get("gameScore") or []
    ht = periods[0] if event["sport"]["id"] == "sr:sport:1" and periods else None
    return {"ft": score, "ht": ht, "status": event.get("matchStatus"), "source": "sportybet"}


def set_result(event_id: str, ft: str, ht: str | None = None, source: str = "manual") -> None:
    res = _load(RESULTS, {})
    res[event_id] = {"ft": ft, "ht": ht, "status": "Ended", "source": source}
    _save(RESULTS, res)


def fetch_results(client, day: str) -> int:
    pred = _load(PREDICTIONS / f"{day}.json", None)
    if not pred:
        return 0
    res, n = _load(RESULTS, {}), 0
    for S in pred["sports"].values():
        for e in S["events"]:
            if e["event_id"] in res:
                continue
            ev = client.event(e["event_id"])
            r = parse_result(ev) if ev else None
            if r:
                res[e["event_id"]] = r
                n += 1
    _save(RESULTS, res)
    return n


# --------------------------------------------------------------- settlement ----

class _Fixed:
    """A one-scoreline 'model' so football pricing masks settle a bet exactly."""

    def __init__(self, h1, a1, h2, a2):
        self.h1, self.a1, self.h2, self.a2 = (np.array([x]) for x in (h1, a1, h2, a2))
        self.h, self.a = self.h1 + self.h2, self.a1 + self.a2
        self.w = np.array([1.0])

    def p(self, mask) -> float:
        return float(self.w[mask].sum())


def settle_one(sport: str, mid: str, spec: str, desc: str, result: dict) -> str | None:
    """Return 'won' | 'lost' | 'push' | 'half_won' | 'half_lost', or None if not settleable."""
    fh, fa = map(int, result["ft"].split(":"))
    if sport == "basketball":
        if mid not in BASKET:
            return None
        margin, total = fh - fa, fh + fa
        mo = re.match(r"^(Over|Under) ([\d.]+)$", desc)
        if mo:
            line = float(mo.group(2))
            val = {"225": total, "227": fh, "228": fa}[mid]
            return "push" if val == line else ("won" if (val > line) == (mo.group(1) == "Over") else "lost")
        if mid in ("219", "11"):
            return "won" if (margin > 0) == (desc == "Home") else "lost"
        hcp = float(re.search(r"hcp=([-\d.]+)", spec).group(1))
        d = (margin + hcp) if desc.startswith("Home") else (-margin - hcp)
        return "push" if d == 0 else ("won" if d > 0 else "lost")
    if mid not in FT_ONLY and not (mid in NEEDS_HT and result.get("ht")):
        return None
    if result.get("ht"):
        h1, a1 = map(int, result["ht"].split(":"))
    else:
        h1, a1 = 0, 0
    model = _Fixed(h1, a1, fh - h1, fa - a1)
    m = Market(mid, "", spec or None, None, [])
    out = fb.price(model, m, desc)  # type: ignore[arg-type]
    if out is None:
        return None
    win, push = out
    return "won" if win > 0.5 else "push" if push > 0.5 else "lost"


PAYOUT = {"won": lambda o: o, "lost": lambda o: 0.0, "push": lambda o: 1.0,
          "half_won": lambda o: (o + 1) / 2, "half_lost": lambda o: 0.5}


# --------------------------------------------------------------------- bets ----

def add_bet(pick: dict, stake: float) -> dict:
    bets = _load(BETS, [])
    bet = {"id": f"b{len(bets) + 1}-{int(dt.datetime.now().timestamp())}", **pick, "stake": stake,
           "status": "open", "payout": None, "placed_at": dt.datetime.now(EAT).isoformat(timespec="minutes")}
    bets.append(bet)
    _save(BETS, bets)
    return bet


def settle_bets() -> int:
    bets, res, n = _load(BETS, []), _load(RESULTS, {}), 0
    for b in bets:
        if b["status"] != "open" or b["event_id"] not in res:
            continue
        s = settle_one(b.get("sport", "football"), b["mid"], b.get("spec", ""), b["desc"], res[b["event_id"]])
        if s:
            b["status"], b["payout"], b["score"] = s, round(b["stake"] * PAYOUT[s](b["odds"]), 2), res[b["event_id"]]["ft"]
            n += 1
    _save(BETS, bets)
    return n


# -------------------------------------------------------------- performance ----

def evaluate() -> dict:
    """Score every saved prediction (all modelled outcomes) against known results."""
    res = _load(RESULTS, {})
    rows: dict[str, list[tuple[float, float, float]]] = {}
    for f in sorted(PREDICTIONS.glob("*.json")):
        pred = json.loads(f.read_text(encoding="utf-8"))
        for sport, S in pred["sports"].items():
            for e in S["events"]:
                r = res.get(e["event_id"])
                if not r:
                    continue
                for m in e["markets"]:
                    if not m.get("odds"):  # model-only price: no stake to score
                        continue
                    s = settle_one(sport, m["mid"], m["spec"], m["desc"], r)
                    if s not in ("won", "lost"):
                        continue
                    rows.setdefault(family(m["mid"]), []).append((m["p"], 1.0 if s == "won" else 0.0, m["odds"]))
    perf, calib = {}, {}
    for fam, xs in rows.items():
        p = np.array([x[0] for x in xs]); y = np.array([x[1] for x in xs]); o = np.array([x[2] for x in xs])
        bins = np.clip((p * 10).astype(int), 0, 9)
        rel = [[float(p[bins == b].mean()), float(y[bins == b].mean()), int((bins == b).sum())]
               for b in range(10) if (bins == b).any()]
        fav = p >= 0.5  # flat 1-unit stake on every selection the model rates >= 50%
        perf[fam] = {"n": len(xs), "brier": round(float(((p - y) ** 2).mean()), 4),
                     "hit_rate_fav": round(float(y[fav].mean()), 4) if fav.any() else None,
                     "roi_fav": round(float((y[fav] * o[fav] - 1).mean()), 4) if fav.any() else None,
                     "reliability": rel}
        if len(xs) >= 200:
            calib[fam] = _isotonic(p, y)
    _save(PERF, perf)
    if calib:
        _save(CALIB, calib)
    return perf


def _isotonic(p: np.ndarray, y: np.ndarray) -> list[list[float]]:
    """Pool-adjacent-violators fit, returned as a monotone piecewise map."""
    order = np.argsort(p)
    xs, ys, ws = list(p[order]), list(y[order]), [1.0] * len(p)
    blocks = [[x, v, w] for x, v, w in zip(xs, ys, ws)]
    out: list[list[float]] = []
    for b in blocks:
        out.append(b)
        while len(out) > 1 and out[-2][1] > out[-1][1]:
            x2, v2, w2 = out.pop()
            x1, v1, w1 = out.pop()
            w = w1 + w2
            out.append([(x1 * w1 + x2 * w2) / w, (v1 * w1 + v2 * w2) / w, w])
    return [[round(float(x), 4), round(float(v), 4)] for x, v, _ in out]


_CAL = None


def calibrate(mid: str, p: float) -> float:
    """Apply the family's isotonic map (if trained), shrunk 50% toward the raw model."""
    global _CAL
    if _CAL is None:
        _CAL = _load(CALIB, {})
    pts = _CAL.get(family(mid))
    if not pts:
        return p
    xs, ys = [a for a, _ in pts], [b for _, b in pts]
    return 0.5 * p + 0.5 * float(np.interp(p, xs, ys))
