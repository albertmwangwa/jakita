"""Tiny dependency-free Nelder-Mead (numpy only)."""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np


def nelder_mead(f: Callable[[np.ndarray], float], x0: Sequence[float], step: Sequence[float] | float = 0.2,
                iters: int = 400, tol: float = 1e-10) -> tuple[np.ndarray, float]:
    x0 = np.asarray(x0, dtype=float)
    n = len(x0)
    steps = np.full(n, step) if np.isscalar(step) else np.asarray(step, dtype=float)
    simplex = [x0] + [x0 + np.eye(n)[i] * steps[i] for i in range(n)]
    vals = [f(x) for x in simplex]
    for _ in range(iters):
        order = np.argsort(vals)
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < tol:
            break
        centroid = np.mean(simplex[:-1], axis=0)
        xr = centroid + (centroid - simplex[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = centroid + 2 * (centroid - simplex[-1])
            fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = centroid + 0.5 * (simplex[-1] - centroid)
            fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:
                best = simplex[0]
                simplex = [best + 0.5 * (s - best) for s in simplex]
                vals = [f(s) for s in simplex]
    i = int(np.argmin(vals))
    return simplex[i], vals[i]
