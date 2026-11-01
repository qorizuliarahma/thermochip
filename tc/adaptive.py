"""
Sampling adaptif: memilih kasus CFD berikutnya yang paling informatif.

Kriteria Expected Improvement (EI) untuk minimasi T_max (Jones, Schonlau, & Welch, 1998,
J. Global Optimization 13(4), 455-492, doi:10.1023/A:1008306431147):

    EI(x) = (T_best - mu(x) - xi) * Phi(z) + sigma(x) * phi(z),   z = (T_best - mu(x) - xi) / sigma(x)

mu dan sigma berasal dari model hibrid Fisika+GP (mu = fisika + rata-rata GP, sigma = deviasi GP).
Kandidat harus memenuhi kendala fabrikasi dan batas pressure drop prediksi.
Usulan dipilih bertahap (greedy) dengan jarak minimum antar-usulan agar tidak menumpuk di satu titik.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, qmc

from .surrogate import FEATURES


def expected_improvement(mu, sigma, best, xi=0.01):
    sigma = np.maximum(sigma, 1e-9)
    imp = best - mu - xi
    z = imp / sigma
    return imp * norm.cdf(z) + sigma * norm.pdf(z)


def suggest_runs(model_T, pred_dP, X_done: pd.DataFrame, T_done, bounds: dict, dP_max: float, fab,
                 n_new: int = 10, n_cand: int = 20000, min_dist: float = 0.12, seed: int = 0) -> pd.DataFrame:
    """model_T: PhysicsResidual yang sudah di-fit. pred_dP: fungsi DataFrame -> Pa."""
    lo = np.array([bounds[f][0] for f in FEATURES]); hi = np.array([bounds[f][1] for f in FEATURES])
    C = pd.DataFrame(qmc.scale(qmc.LatinHypercube(d=4, seed=seed).random(n_cand), lo, hi), columns=FEATURES)
    ok = (C.w_mm >= fab.w_min) & (C.t_mm >= fab.t_min) & (C.H_mm / C.w_mm <= fab.AR_max)
    C = C[ok].reset_index(drop=True)
    C["dP_pred"] = pred_dP(C[FEATURES])
    C = C[C.dP_pred <= dP_max].reset_index(drop=True)
    mu, sd = model_T.predict(C[FEATURES], return_std=True)
    feas_done = pred_dP(X_done[FEATURES]) <= dP_max
    best = float(np.min(np.asarray(T_done)[feas_done])) if feas_done.any() else float(np.min(T_done))
    C["T_pred"], C["T_std"], C["EI"] = mu, sd, expected_improvement(mu, sd, best)
    Z = (C[FEATURES].values - lo) / (hi - lo)
    Zd = (X_done[FEATURES].values - lo) / (hi - lo)
    chosen = []
    for i in np.argsort(-C.EI.values):
        ref = np.vstack([Zd] + [Z[j][None] for j in chosen])
        if np.min(np.linalg.norm(ref - Z[i], axis=1)) >= min_dist:
            chosen.append(i)
        if len(chosen) == n_new:
            break
    out = C.iloc[chosen].copy()
    out.insert(0, "run", [f"A{k + 1:02d}" for k in range(len(out))])
    for f in FEATURES:
        out[f] = out[f].round(2)
    return out.round({"dP_pred": 0, "T_pred": 2, "T_std": 3, "EI": 4}), best
