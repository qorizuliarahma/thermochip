"""
Optimasi desain cold plate pada model surrogate dengan kendala fabrikasi.

    minimasi   T_max(w, t, H, V)
    kendala    dP(w, t, H, V) <= dP_max
               w >= w_min (alat potong CNC), t >= t_min (kekakuan sirip), H/w <= AR_max

Diselesaikan dengan Differential Evolution (scipy) memakai fungsi penalti.
Front Pareto diperoleh dengan menyapu nilai dP_max.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

from .surrogate import FEATURES


@dataclass
class FabLimits:
    w_min: float = 0.5      # mm
    t_min: float = 0.3      # mm
    AR_max: float = 10.0    # H/w maksimum


def optimize(pred_T, pred_dP, bounds: dict, dP_max: float, fab: FabLimits, seed: int = 0):
    b = [(max(bounds["w_mm"][0], fab.w_min), bounds["w_mm"][1]),
         (max(bounds["t_mm"][0], fab.t_min), bounds["t_mm"][1]),
         bounds["H_mm"], bounds["flow_lpm"]]

    def obj(x):
        # x berbentuk (4, S): seluruh populasi dievaluasi sekaligus (vectorized)
        X = pd.DataFrame(np.atleast_2d(x).reshape(4, -1).T, columns=FEATURES)
        T, dP = np.asarray(pred_T(X)), np.asarray(pred_dP(X))
        pen = np.maximum(0.0, dP / dP_max - 1.0) * 1e3 + np.maximum(0.0, X.H_mm / X.w_mm - fab.AR_max).values * 1e2
        return T + pen

    r = differential_evolution(obj, b, seed=seed, tol=1e-7, maxiter=200, popsize=15, polish=False,
                               vectorized=True, updating="deferred")
    X = pd.DataFrame([r.x], columns=FEATURES)
    dP = float(pred_dP(X)[0])
    return {k: float(v) for k, v in zip(FEATURES, r.x)} | {"T_max": float(pred_T(X)[0]), "dP": dP,
                                                            "feasible": bool(dP <= dP_max * 1.001)}


def pareto_sweep(pred_T, pred_dP, bounds, fab, dP_values):
    return pd.DataFrame([optimize(pred_T, pred_dP, bounds, d, fab) | {"dP_max": d} for d in dP_values])
