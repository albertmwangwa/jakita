"""Aggregate tipster / model / prediction-market picks into per-market sentiment."""
from __future__ import annotations

import re
from collections import defaultdict

# Map research "market" labels to (SportyBet market id, spec, outcome desc builder).
_ONE_X_TWO = {"1": "Home", "X": "Draw", "2": "Away"}


def to_key(market: str, pick: str) -> tuple[str, str, str] | None:
    m = market.strip().lower()
    p = pick.strip()
    if m == "1x2":
        d = _ONE_X_TWO.get(p.upper())
        return ("1", "", d) if d else None
    mo = re.match(r"^(corners |cards |home |away )?o/u ([\d.]+)$", m)
    if mo:
        kind, line = (mo.group(1) or "").strip(), mo.group(2)
        mid = {"": "18", "corners": "166", "cards": "139", "home": "19", "away": "20"}[kind]
        side = "Over" if p.lower().startswith("over") else "Under"
        return mid, f"total={line}", f"{side} {line}"
    if m in ("gg/ng", "btts"):
        return "29", "", "Yes" if p.upper() in ("GG", "YES") else "No"
    if m == "correct score":
        mm = re.match(r"^(\d+)\s*[-:]\s*(\d+)", p)
        if mm:
            # "2-1 Haiti" style picks are home-first already in our sources
            return "45", "", f"{mm.group(1)}:{mm.group(2)}"
    return None


def aggregate(tipsters: list[dict]) -> list[dict]:
    """Group picks by market key; numeric probabilities are averaged where given."""
    groups: dict[tuple, dict] = defaultdict(lambda: {"sources": [], "probs": []})
    for t in tipsters:
        key = to_key(t.get("market", ""), t.get("pick", ""))
        if not key:
            continue
        g = groups[key]
        g["sources"].append(t["source"])
        prob = t.get("prob") or {}
        val = None
        if key[0] == "1":
            val = prob.get({"Home": "1", "Draw": "X", "Away": "2"}[key[2]])
        elif key[0] in ("18", "166", "139", "19", "20"):
            val = prob.get(key[2].split()[0])
        elif key[0] == "29":
            val = prob.get(key[2])
        if val is not None:
            g["probs"].append(float(val))
    out = []
    for (mid, spec, desc), g in groups.items():
        out.append({"market_id": mid, "spec": spec, "desc": desc, "votes": len(g["sources"]),
                    "sources": g["sources"], "avg_prob": sum(g["probs"]) / len(g["probs"]) if g["probs"] else None})
    return sorted(out, key=lambda x: -x["votes"])


def one_x_two_consensus(tipsters: list[dict]) -> tuple[list[float], int] | None:
    """Average full 1X2 distributions from sources that published all three numbers (or 1 & 2)."""
    rows = []
    for t in tipsters:
        if t.get("market") != "1X2" or not t.get("prob"):
            continue
        p = t["prob"]
        if "1" in p and "2" in p:
            x = p.get("X", max(0.0, 1 - p["1"] - p["2"]))
            s = p["1"] + x + p["2"]
            rows.append([p["1"] / s, x / s, p["2"] / s])
    if not rows:
        return None
    n = len(rows)
    return [sum(r[i] for r in rows) / n for i in range(3)], n
