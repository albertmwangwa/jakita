"""Football goal model.

A Dixon-Coles adjusted Poisson model whose parameters (home/away goal rates, low-score
correlation rho and first-half share of goals) are fitted to the bookmaker's own de-vigged
main markets. Every derived goal market (correct score, HT/FT, halves, combos, margins,
multigoals...) is then repriced from one consistent joint distribution of
(home 1H, away 1H, home 2H, away 2H) goals, so prices that disagree with the main markets
stand out.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from ..markets import Market
from .optim import nelder_mead

N = 9  # goals per team per half considered (0..8)


def _pois(lam: float, n: int = N) -> np.ndarray:
    lam = max(lam, 1e-6)
    k = np.arange(n)
    p = np.exp(-lam + k * math.log(lam) - np.array([math.lgamma(i + 1) for i in k]))
    return p / p.sum()


def _ft_matrix(lh: float, la: float, rho: float, n: int = 12) -> np.ndarray:
    m = np.outer(_pois(lh, n), _pois(la, n))
    m[0, 0] *= 1 - lh * la * rho
    m[0, 1] *= 1 + lh * rho
    m[1, 0] *= 1 + la * rho
    m[1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    return m / m.sum()


@dataclass
class GoalModel:
    lh: float
    la: float
    rho: float
    share1: float  # share of goals expected in the first half
    fit_error: float = 0.0

    def __post_init__(self) -> None:
        g = np.arange(N)
        H1, A1, H2, A2 = np.meshgrid(g, g, g, g, indexing="ij")
        w = (np.multiply.outer(np.multiply.outer(_pois(self.lh * self.share1), _pois(self.la * self.share1)),
                               np.multiply.outer(_pois(self.lh * (1 - self.share1)), _pois(self.la * (1 - self.share1)))))
        h, a = H1 + H2, A1 + A2
        # Dixon-Coles low-score correction applied on the full-time score.
        tau = np.ones_like(w)
        tau[(h == 0) & (a == 0)] = 1 - self.lh * self.la * self.rho
        tau[(h == 0) & (a == 1)] = 1 + self.lh * self.rho
        tau[(h == 1) & (a == 0)] = 1 + self.la * self.rho
        tau[(h == 1) & (a == 1)] = 1 - self.rho
        w = np.clip(w * tau, 0, None)
        w /= w.sum()
        self.w = w.ravel()
        self.h1, self.a1, self.h2, self.a2 = H1.ravel(), A1.ravel(), H2.ravel(), A2.ravel()
        self.h, self.a = self.h1 + self.h2, self.a1 + self.a2

    def p(self, mask: np.ndarray) -> float:
        return float(self.w[mask].sum())

    @property
    def xg(self) -> tuple[float, float]:
        return float((self.w * self.h).sum()), float((self.w * self.a).sum())

    def top_scores(self, k: int = 5) -> list[tuple[str, float]]:
        acc: dict[tuple[int, int], float] = {}
        for hh, aa, ww in zip(self.h, self.a, self.w):
            acc[(int(hh), int(aa))] = acc.get((int(hh), int(aa)), 0.0) + float(ww)
        best = sorted(acc.items(), key=lambda kv: -kv[1])[:k]
        return [(f"{s[0]}:{s[1]}", p) for s, p in best]


# ---------------------------------------------------------------- fitting ----

def _fair(m: Market, desc: str) -> float | None:
    for o in m.outcomes:
        if o.desc == desc:
            return o.fair
    return None


def _line(m: Market) -> float | None:
    v = m.spec_value("total")
    return float(v) if v is not None else None


def fit(by_id: dict[str, list[Market]], overrides: dict | None = None) -> GoalModel | None:
    """overrides: optional blended targets {"1x2": [h, d, a], "o25": p, "btts": p}."""
    overrides = overrides or {}
    m1 = (by_id.get("1") or [None])[0]
    if m1 is None:
        return None
    target_1x2 = [_fair(m1, d) for d in ("Home", "Draw", "Away")]
    if None in target_1x2:
        return None
    target_1x2 = overrides.get("1x2", target_1x2)

    totals = []  # (side, line, P(over | no push)) side: 'T','H','A'
    for mid, side in (("18", "T"), ("19", "H"), ("20", "A")):
        for m in by_id.get(mid, []):
            line = _line(m)
            if line is None:
                continue
            po = _fair(m, f"Over {m.spec_value('total')}")
            if side == "T" and abs(line - 2.5) < 1e-9 and "o25" in overrides:
                po = overrides["o25"]
            if po is not None:
                totals.append((side, line, po))
    btts = None
    if by_id.get("29"):
        btts = _fair(by_id["29"][0], "Yes")
    btts = overrides.get("btts", btts)

    def ft_loss(x: np.ndarray) -> float:
        lh, la, rho = math.exp(x[0]), math.exp(x[1]), max(-0.2, min(0.1, x[2]))
        M = _ft_matrix(lh, la, rho)
        n = M.shape[0]
        i, j = np.indices(M.shape)
        ph, pd = float(M[i > j].sum()), float(np.trace(M))
        pa = 1 - ph - pd
        loss = 3 * sum((a - b) ** 2 for a, b in zip((ph, pd, pa), target_1x2))
        for side, line, po in totals:
            g = i + j if side == "T" else (i if side == "H" else j)
            over, under = float(M[g > line].sum()), float(M[g < line].sum())
            if over + under <= 0:
                continue
            loss += (over / (over + under) - po) ** 2 * (2 if abs(line - 2.5) < 1e-9 else 1)
        if btts is not None:
            loss += 2 * (float(M[1:, 1:].sum()) - btts) ** 2
        return loss

    # Start: total from the most balanced line, split by 1X2 strength.
    tot0 = 2.6
    sup = (target_1x2[0] - target_1x2[2]) * 2.0
    x0 = np.array([math.log(max(0.2, tot0 / 2 + sup / 2)), math.log(max(0.2, tot0 / 2 - sup / 2)), -0.05])
    x, err = nelder_mead(ft_loss, x0, step=[0.3, 0.3, 0.05])
    lh, la, rho = math.exp(x[0]), math.exp(x[1]), max(-0.2, min(0.1, x[2]))

    # First-half share from HT markets.
    ht = []
    for m in by_id.get("68", []):
        line = _line(m)
        po = _fair(m, f"Over {m.spec_value('total')}") if line is not None else None
        if po is not None:
            ht.append((line, po))
    m60 = (by_id.get("60") or [None])[0]
    ht_draw = _fair(m60, "Draw") if m60 else None

    def ht_loss(s: float) -> float:
        M = _ft_matrix(lh * s, la * s, 0.0)
        i, j = np.indices(M.shape)
        loss = 0.0
        for line, po in ht:
            over, under = float(M[i + j > line].sum()), float(M[i + j < line].sum())
            loss += (over / max(over + under, 1e-9) - po) ** 2
        if ht_draw is not None:
            loss += (float(np.trace(M)) - ht_draw) ** 2
        return loss

    share = 0.45
    if ht or ht_draw is not None:
        share = min((s / 100 for s in range(36, 53)), key=ht_loss)
    return GoalModel(lh, la, rho, share, fit_error=float(err))


# ---------------------------------------------------------------- pricing ----

def _ou(desc: str) -> tuple[str, float] | None:
    m = re.match(r"^(Over|Under) ([\d.]+)$", desc)
    return (m.group(1), float(m.group(2))) if m else None


def _settle_line(diff: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    """diff > 0 win, == 0 push (whole lines)."""
    return float(w[diff > 1e-9].sum()), float(w[np.abs(diff) <= 1e-9].sum())


def price(gm: GoalModel, m: Market, desc: str) -> tuple[float, float] | None:
    """Return (P(win), P(push)) for one outcome, or None if the market is not modelled."""
    h, a, h1, a1, h2, a2, w = gm.h, gm.a, gm.h1, gm.a1, gm.h2, gm.a2, gm.w
    res = {"Home": h > a, "Draw": h == a, "Away": h < a}
    res1 = {"Home": h1 > a1, "Draw": h1 == a1, "Away": h1 < a1}
    res2 = {"Home": h2 > a2, "Draw": h2 == a2, "Away": h2 < a2}
    dc = {"Home or Draw": h >= a, "Home or Away": h != a, "Draw or Away": h <= a,
          "Home/Draw": h >= a, "Home/Away": h != a, "Draw/Away": h <= a}
    yes_no = lambda mask: {"Yes": mask, "No": ~mask}  # noqa: E731
    mid = m.id
    P = lambda mask: (gm.p(mask), 0.0)  # noqa: E731

    def total_of(goals: np.ndarray):
        ou = _ou(desc)
        if not ou:
            return None
        side, line = ou
        return _settle_line((goals - line) if side == "Over" else (line - goals), w)

    def no_bet(excluded: np.ndarray, mask: np.ndarray):
        return gm.p(mask & ~excluded), gm.p(excluded)

    try:
        if mid in ("1",):
            return P(res[desc])
        if mid == "10":
            return P(dc[desc])
        if mid == "11":
            return no_bet(h == a, res[desc])
        if mid == "12":
            return no_bet(h > a, res[desc])
        if mid == "13":
            return no_bet(h < a, res[desc])
        if mid == "18":
            return total_of(h + a)
        if mid == "19":
            return total_of(h)
        if mid == "20":
            return total_of(a)
        if mid == "68":
            return total_of(h1 + a1)
        if mid == "69":
            return total_of(h1)
        if mid == "70":
            return total_of(a1)
        if mid == "90":
            return total_of(h2 + a2)
        if mid == "91":
            return total_of(h2)
        if mid == "92":
            return total_of(a2)
        if mid == "29":
            return P(yes_no((h > 0) & (a > 0))[desc])
        if mid == "75":
            return P(yes_no((h1 > 0) & (a1 > 0))[desc])
        if mid == "95":
            return P(yes_no((h2 > 0) & (a2 > 0))[desc])
        if mid == "60":
            return P(res1[desc])
        if mid == "83":
            return P(res2[desc])
        if mid == "63":
            return P({"Home or Draw": h1 >= a1, "Home or Away": h1 != a1, "Draw or Away": h1 <= a1}[desc])
        if mid == "85":
            return P({"Home or Draw": h2 >= a2, "Home or Away": h2 != a2, "Draw or Away": h2 <= a2}[desc])
        if mid == "64":
            return no_bet(h1 == a1, res1[desc])
        if mid == "86":
            return no_bet(h2 == a2, res2[desc])
        if mid == "26":
            return P({"Odd": (h + a) % 2 == 1, "Even": (h + a) % 2 == 0}[desc])
        if mid == "27":
            return P({"Odd": h % 2 == 1, "Even": h % 2 == 0}[desc])
        if mid == "28":
            return P({"Odd": a % 2 == 1, "Even": a % 2 == 0}[desc])
        if mid == "74":
            return P({"Odd": (h1 + a1) % 2 == 1, "Even": (h1 + a1) % 2 == 0}[desc])
        if mid == "31":
            return P(yes_no(a == 0)[desc])
        if mid == "32":
            return P(yes_no(h == 0)[desc])
        if mid == "33":
            return P(yes_no((h > a) & (a == 0))[desc])
        if mid == "34":
            return P(yes_no((a > h) & (h == 0))[desc])
        if mid == "30":
            return P({"None": (h == 0) & (a == 0), "Only Home": (h > 0) & (a == 0),
                      "Only Away": (h == 0) & (a > 0), "Both teams": (h > 0) & (a > 0)}[desc])
        if mid in ("45", "81", "98"):
            sh, sa = {"45": (h, a), "81": (h1, a1), "98": (h2, a2)}[mid]
            mm = re.match(r"^(\d+):(\d+)$", desc)
            if not mm:
                return None
            return P((sh == int(mm.group(1))) & (sa == int(mm.group(2))))
        if mid == "47":
            x, y = desc.split("/")
            return P(res1[x] & res[y])
        if mid in ("21", "23", "24", "71", "93"):
            g = {"21": h + a, "23": h, "24": a, "71": h1 + a1, "93": h2 + a2}[mid]
            if desc.endswith("+"):
                return P(g >= int(desc[:-1]))
            return P(g == int(desc))
        if mid == "25":
            if desc.endswith("+"):
                return P(h + a >= int(desc[:-1]))
            lo, hi = map(int, desc.split("-"))
            return P((h + a >= lo) & (h + a <= hi))
        if mid in ("548", "549", "550", "552", "553"):
            g = {"548": h + a, "549": h, "550": a, "552": h1 + a1, "553": h2 + a2}[mid]
            if desc == "No goal":
                return P(g == 0)
            if desc.endswith("+"):
                return P(g >= int(desc[:-1]))
            lo, hi = map(int, desc.split("-"))
            return P((g >= lo) & (g <= hi))
        if mid == "15":
            mm = re.match(r"^(Home|Away) by (\d+)(\+?)$", desc)
            if desc == "Draw":
                return P(h == a)
            if not mm:
                return None
            d = (h - a) if mm.group(1) == "Home" else (a - h)
            k = int(mm.group(2))
            return P(d >= k) if mm.group(3) else P(d == k)
        if mid == "14":  # 3-way handicap hcp=x:y
            x, y = map(int, m.spec_value("hcp").split(":"))
            side = desc.split(" ")[0]
            hh, aa = h + x, a + y
            return P({"Home": hh > aa, "Draw": hh == aa, "Away": hh < aa}[side])
        if mid in ("16", "66", "88"):  # Asian handicap, half or whole lines
            line = float(m.spec_value("hcp"))
            if abs((line * 2) % 1) > 1e-9:  # quarter lines not modelled
                return None
            sh, sa = {"16": (h, a), "66": (h1, a1), "88": (h2, a2)}[mid]
            if desc.startswith("Home"):
                return _settle_line(sh + line - sa, w)
            return _settle_line(sa - line - sh, w)
        if mid == "35":
            r, b = desc.split(" & ")
            return P(res[r] & yes_no((h > 0) & (a > 0))[b])
        if mid == "36":
            ou, b = desc.split(" & ")
            side, line = _ou(ou)
            g = h + a
            return P(((g > line) if side == "Over" else (g < line)) & yes_no((h > 0) & (a > 0))[b])
        if mid in ("37", "547"):
            r, ou = desc.split(" & ")
            side, line = _ou(ou)
            g = h + a
            base = res[r] if mid == "37" else dc[r]
            return P(base & ((g > line) if side == "Over" else (g < line)))
        if mid == "546":
            r, b = desc.split(" & ")
            return P(dc[r] & yes_no((h > 0) & (a > 0))[b])
        if mid == "48":
            return P(yes_no((h1 > a1) & (h2 > a2))[desc])
        if mid == "49":
            return P(yes_no((a1 > h1) & (a2 > h2))[desc])
        if mid == "50":
            return P(yes_no((h1 > a1) | (h2 > a2))[desc])
        if mid == "51":
            return P(yes_no((a1 > h1) | (a2 > h2))[desc])
        if mid == "56":
            return P(yes_no((h1 > 0) & (h2 > 0))[desc])
        if mid == "57":
            return P(yes_no((a1 > 0) & (a2 > 0))[desc])
        if mid == "55":
            x, y = desc.split("/")
            b1, b2 = (h1 > 0) & (a1 > 0), (h2 > 0) & (a2 > 0)
            return P((b1 if x == "Yes" else ~b1) & (b2 if y == "Yes" else ~b2))
        if mid == "52":
            g1, g2 = h1 + a1, h2 + a2
            return P({"1st half": g1 > g2, "2nd half": g2 > g1, "equal": g1 == g2}[desc])
        if mid in ("58", "59"):
            line = float(m.spec_value("total"))
            g1, g2 = h1 + a1, h2 + a2
            mask = ((g1 > line) & (g2 > line)) if mid == "58" else ((g1 < line) & (g2 < line))
            return P(yes_no(mask)[desc])
        if mid == "900984":
            return P(yes_no((h1 + a1 > 0) & (h2 + a2 > 0))[desc])
    except (KeyError, ValueError, AttributeError, TypeError):
        return None
    return None
