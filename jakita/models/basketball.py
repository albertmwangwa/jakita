"""Basketball: normal models for margin and points, fitted to handicap/total ladders."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..markets import Market
from .optim import nelder_mead


def Phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


@dataclass
class Normal:
    mu: float
    sigma: float

    def gt(self, x: float) -> float:
        return 1 - Phi((x - self.mu) / self.sigma)


def _fit(points: list[tuple[float, float]], mu0: float, sig0: float, sig_bounds: tuple[float, float]) -> Normal | None:
    """points: (x, P(X > x))."""
    if not points:
        return None

    def loss(v):
        s = min(max(v[1], sig_bounds[0]), sig_bounds[1])
        return sum((1 - Phi((x - v[0]) / s) - p) ** 2 for x, p in points)

    # Start at the line priced closest to 50/50 and try several spreads; a flat loss
    # surface otherwise lets the simplex run sigma into its bound.
    mu0 = min(points, key=lambda t: abs(t[1] - 0.5))[0] if len(points) > 1 else mu0
    best = None
    for k in (0.75, 1.0, 1.25):
        v, err = nelder_mead(loss, [mu0, sig0 * k], step=[2.0, 1.0])
        if best is None or err < best[1]:
            best = (v, err)
    v = best[0]
    return Normal(float(v[0]), float(min(max(v[1], sig_bounds[0]), sig_bounds[1])))


def _over_points(markets: list[Market]) -> list[tuple[float, float]]:
    pts = []
    for m in markets:
        v = m.spec_value("total")
        for o in m.outcomes:
            if v is not None and o.desc == f"Over {v}":
                pts.append((float(v), o.fair))
    return pts


def _margin_points(markets: list[Market]) -> list[tuple[float, float]]:
    """Handicap ladder: home covers -h  <=> margin > -h... spec hcp is home line."""
    pts = []
    for m in markets:
        v = m.spec_value("hcp")
        if v is None:
            continue
        for o in m.outcomes:
            if o.desc.startswith("Home"):
                pts.append((-float(v), o.fair))  # P(margin > -hcp)
    return pts


@dataclass
class BasketModel:
    margin: Normal
    total: Normal
    home_pts: Normal | None
    away_pts: Normal | None
    margin_1h: Normal | None
    total_1h: Normal | None
    home_name: str = ""

    def summary(self) -> dict:
        return {"exp_margin": round(self.margin.mu, 1), "margin_sd": round(self.margin.sigma, 1),
                "exp_total": round(self.total.mu, 1), "total_sd": round(self.total.sigma, 1),
                "exp_home": round(self.home_pts.mu, 1) if self.home_pts else round((self.total.mu + self.margin.mu) / 2, 1),
                "exp_away": round(self.away_pts.mu, 1) if self.away_pts else round((self.total.mu - self.margin.mu) / 2, 1)}

    def price(self, m: Market, desc: str) -> tuple[float, float] | None:
        mid = m.id
        mo = re.match(r"^(Over|Under) ([\d.]+)$", desc)
        dist = {"225": self.total, "227": self.home_pts, "228": self.away_pts, "68": self.total_1h}.get(mid)
        if mo and dist is not None:
            line = float(mo.group(2))
            p = dist.gt(line)
            return (p if mo.group(1) == "Over" else 1 - p), 0.0
        if mid in ("219", "11"):
            p = self.margin.gt(0)
            return {"Home": (p, 0.0), "Away": (1 - p, 0.0)}.get(desc)
        if mid in ("223", "66"):
            dist = self.margin if mid == "223" else self.margin_1h
            if dist is None:
                return None
            line = float(m.spec_value("hcp"))
            p = dist.gt(-line)
            return (p, 0.0) if desc.startswith("Home") else (1 - p, 0.0)
        if mid == "290":
            # Outcomes look like "Home by 1-5", "<Team> by 11+", or "other".
            mm = re.match(r"^(.*) by (\d+)(?:-(\d+)|(\+))$", desc)
            if not mm:
                return None
            who, lo = mm.group(1), int(mm.group(2))
            hi = int(mm.group(3)) if mm.group(3) else None
            home = who == "Home" or (self.home_name and who == self.home_name)
            m_ = self.margin if home else Normal(-self.margin.mu, self.margin.sigma)
            p = m_.gt(lo - 0.5) - (m_.gt(hi + 0.5) if hi is not None else 0.0)
            return p, 0.0
        return None


def fit(by_id: dict[str, list[Market]], nba: bool, home_name: str = "") -> BasketModel | None:
    sig_m, sig_t = (12.5, 18.0) if nba else (11.0, 15.0)
    mpts = _margin_points(by_id.get("223", []))
    if by_id.get("219"):
        for o in by_id["219"][0].outcomes:
            if o.desc == "Home":
                mpts.append((0.0, o.fair))
    tpts = _over_points(by_id.get("225", []))
    if not mpts or not tpts:
        return None
    mu_t0 = sorted(tpts, key=lambda t: abs(t[1] - 0.5))[0][0]
    margin = _fit(mpts, 0.0, sig_m, (sig_m * 0.7, sig_m * 1.4))
    total = _fit(tpts, mu_t0, sig_t, (sig_t * 0.6, sig_t * 1.5))
    hp, ap = _over_points(by_id.get("227", [])), _over_points(by_id.get("228", []))
    home = _fit(hp, (total.mu + margin.mu) / 2, sig_t * 0.65, (5, 20)) if hp else None
    away = _fit(ap, (total.mu - margin.mu) / 2, sig_t * 0.65, (5, 20)) if ap else None
    t1 = _over_points(by_id.get("68", []))
    total_1h = _fit(t1, total.mu / 2, sig_t * 0.7, (5, 20)) if t1 else None
    m1 = _margin_points(by_id.get("66", []))
    margin_1h = _fit(m1, margin.mu / 2, sig_m * 0.7, (4, 15)) if m1 else None
    return BasketModel(margin, total, home, away, margin_1h, total_1h, home_name)
