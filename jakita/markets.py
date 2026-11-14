"""Normalise SportyBet market books and remove bookmaker margin."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Outcome:
    desc: str
    odds: float
    sb_prob: float | None = None  # SportyBet's own probability field
    fair: float | None = None  # de-vigged within its market


@dataclass
class Market:
    id: str
    name: str
    spec: str | None
    group: str | None
    outcomes: list[Outcome] = field(default_factory=list)
    margin: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.id}|{self.spec or ''}"

    def spec_value(self, name: str) -> str | None:
        if not self.spec:
            return None
        for part in self.spec.split("|"):
            k, _, v = part.partition("=")
            if k == name:
                return v
        return None


def devig(odds: list[float]) -> tuple[list[float], float]:
    """Power-method de-vig: p_i = (1/o_i)^k with k chosen so sum(p) == 1."""
    inv = [1.0 / o for o in odds]
    over = sum(inv)
    margin = over - 1.0
    if len(odds) < 2 or over <= 1.0:
        return [p / over for p in inv], margin
    lo, hi = 1.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        s = sum(p ** k for p in inv)
        if s > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    probs = [p ** k for p in inv]
    s = sum(probs)
    return [p / s for p in probs], margin


def parse_markets(event: dict) -> list[Market]:
    out: list[Market] = []
    for m in event.get("markets", []):
        if m.get("status", 0) not in (0, None):  # 0 = open
            continue
        outs = []
        for o in m.get("outcomes", []):
            if o.get("isActive", 1) != 1:
                continue
            try:
                odds = float(o["odds"])
            except (KeyError, ValueError):
                continue
            if odds <= 1.0:
                continue
            sb = o.get("probability")
            outs.append(Outcome(o.get("desc", "").strip(), odds, float(sb) if sb else None))
        if len(outs) < 2:
            continue
        fair, margin = devig([o.odds for o in outs])
        for o, p in zip(outs, fair):
            o.fair = p
        out.append(Market(str(m["id"]), (m.get("name") or m.get("desc") or "").strip(), m.get("specifier"),
                          m.get("group"), outs, margin))
    return out


def index(markets: list[Market]) -> dict[str, list[Market]]:
    by_id: dict[str, list[Market]] = {}
    for m in markets:
        by_id.setdefault(m.id, []).append(m)
    return by_id
