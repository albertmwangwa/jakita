"""Negative-binomial models for count markets (corners, bookings, shots, fouls, offsides).

Each O/U ladder is fitted on its own (mean + dispersion). Team ladders, when present, give
home/away means that drive the 1X2 and handicap versions of the same stat. An external
average (e.g. from a stats site) can be blended into the mean.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from ..markets import Market
from .optim import nelder_mead

KMAX = 80

# family -> (total ladder id, home ladder id, away ladder id, 1x2 id, handicap id)
FAMILIES = {
    "corners": ("166", "900300", "900301", "162", "165"),
    "corners_1h": ("177", "900302", "900303", "173", "176"),
    "bookings": ("139", "900304", "900305", "136", "900312"),
    "bookings_1h": ("152", "900306", "900307", "149", None),
    "shots": ("900394", "900552", "900553", "900320", None),
    "shots_on_target": ("900393", "900546", "900547", "900318", None),
    "fouls": ("900342", "900544", "900545", "900539", None),
    "offsides": ("900396", "900568", "900569", "900570", None),
}


def nb_pmf(mu: float, r: float, kmax: int = KMAX) -> np.ndarray:
    mu, r = max(mu, 1e-6), max(r, 1e-3)
    k = np.arange(kmax)
    logp = (np.array([math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1) for i in k])
            + r * math.log(r / (r + mu)) + k * math.log(mu / (r + mu)))
    p = np.exp(logp)
    return p / p.sum()


@dataclass
class CountDist:
    mu: float
    r: float
    err: float = 0.0

    @property
    def pmf(self) -> np.ndarray:
        return nb_pmf(self.mu, self.r)


def _ladder(markets: list[Market]) -> list[tuple[float, float]]:
    pts = []
    for m in markets:
        v = m.spec_value("total")
        if v is None:
            continue
        for o in m.outcomes:
            if o.desc == f"Over {v}":
                pts.append((float(v), o.fair))
    return pts


def fit_ladder(markets: list[Market], prior_mu: float | None = None, prior_w: float = 0.3) -> CountDist | None:
    pts = _ladder(markets)
    if not pts:
        return None

    def loss(x):
        p = nb_pmf(math.exp(x[0]), math.exp(x[1]))
        k = np.arange(len(p))
        e = 0.0
        for line, po in pts:
            over, under = p[k > line].sum(), p[k < line].sum()
            e += (over / max(over + under, 1e-9) - po) ** 2
        return e

    mid = sorted(pts, key=lambda t: abs(t[1] - 0.5))[0][0]
    x, err = nelder_mead(loss, [math.log(max(mid, 0.3)), math.log(15.0)], step=[0.2, 0.8])
    mu, r = math.exp(x[0]), min(math.exp(x[1]), 500.0)
    if prior_mu:
        mu = (1 - prior_w) * mu + prior_w * prior_mu
    return CountDist(mu, r, float(err))


@dataclass
class CountModel:
    family: str
    total: CountDist | None
    home: CountDist | None
    away: CountDist | None

    def _joint(self) -> tuple[np.ndarray, np.ndarray] | None:
        if not (self.home and self.away):
            return None
        return self.home.pmf, self.away.pmf

    def summary(self) -> dict:
        return {"total_mean": round(self.total.mu, 2) if self.total else None,
                "home_mean": round(self.home.mu, 2) if self.home else None,
                "away_mean": round(self.away.mu, 2) if self.away else None}

    def price(self, m: Market, desc: str) -> tuple[float, float] | None:
        tid, hid, aid, x12, hcp = FAMILIES[self.family]
        mo = re.match(r"^(Over|Under) ([\d.]+)$", desc)
        dist = {tid: self.total, hid: self.home, aid: self.away}.get(m.id)
        if mo and dist is not None:
            p = dist.pmf
            k = np.arange(len(p))
            line = float(mo.group(2))
            win = p[k > line].sum() if mo.group(1) == "Over" else p[k < line].sum()
            return float(win), float(p[k == line].sum())
        j = self._joint()
        if j is None:
            return None
        ph, pa = j
        D = np.subtract.outer(np.arange(len(ph)), np.arange(len(pa)))
        W = np.outer(ph, pa)
        if m.id == x12:
            mask = {"Home": D > 0, "Draw": D == 0, "Away": D < 0}.get(desc)
            return (float(W[mask].sum()), 0.0) if mask is not None else None
        if hcp and m.id == hcp:
            mm = re.search(r"\(?([+-]?[\d.]+)\)?$", desc)
            if not mm:
                return None
            line = float(mm.group(1))
            diff = (D + line) if desc.startswith("Home") else (-D + line)
            return float(W[diff > 1e-9].sum()), float(W[np.abs(diff) <= 1e-9].sum())
        return None


def fit_all(by_id: dict[str, list[Market]], priors: dict[str, float] | None = None) -> dict[str, CountModel]:
    priors = priors or {}
    out = {}
    for fam, (tid, hid, aid, _x12, _h) in FAMILIES.items():
        tot = fit_ladder(by_id.get(tid, []), priors.get(fam))
        home = fit_ladder(by_id.get(hid, []))
        away = fit_ladder(by_id.get(aid, []))
        if tot is None and home and away:
            tot = CountDist(home.mu + away.mu, (home.r + away.r) / 2)
        if tot or home or away:
            out[fam] = CountModel(fam, tot, home, away)
    return out


def family_of(market_id: str) -> str | None:
    for fam, ids in FAMILIES.items():
        if market_id in ids:
            return fam
    return None
