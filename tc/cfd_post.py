"""
Pengolahan hasil CFD: besaran turunan, neraca energi, dan perbandingan dengan teori.

Masukan  : data/cfd_results.csv (satu baris per run)
Kolom wajib : run, w_mm, t_mm, H_mm, flow_lpm, T_max_cfd, dP_cfd
Kolom opsional : Q_W (default 300), T_in_C (default 25), T_out_cfd, dP_channel_cfd, mesh_elements

Besaran yang dihitung untuk tiap run:
  R_th       = (T_max - T_in) / Q                           hambatan termal total [TP81]
  E_err      = (rho V cp (T_out - T_in) - Q) / Q            cek neraca energi (target |E_err| < 2%)
  P_pump     = dP V                                         daya pompa hidraulik
  R_conv,eff = R_th - R_cond - R_heat                       hambatan konveksi efektif dari CFD
  Nu_eff     = h_eff Dh / k_f, h_eff dari balik model sirip  dibandingkan Nu korelasi [SL78]
  fRe_app    = dP_channel Dh / (2 L rho v^2) * Re            dibandingkan korelasi Shah [S78]
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .correlations import h_from_R_conv, thermal_model
from .geometry import PlateSpec, lpm_to_m3s, make_channels
from .properties import Fluid, Solid

REQUIRED = ["run", "w_mm", "t_mm", "H_mm", "flow_lpm", "T_max_cfd", "dP_cfd"]


def load_cfd(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ada di {path}: {missing}")
    df = df.dropna(subset=["T_max_cfd", "dP_cfd"]).copy()
    if df.empty:
        raise ValueError("Belum ada run yang terisi hasil T_max_cfd dan dP_cfd.")
    df["Q_W"] = df.get("Q_W", pd.Series(300.0, index=df.index)).fillna(300.0)
    df["T_in_C"] = df.get("T_in_C", pd.Series(25.0, index=df.index)).fillna(25.0)
    return df.reset_index(drop=True)


@dataclass
class PostSummary:
    n_runs: int
    T_mae_model: float
    T_bias_model: float
    dP_mape_model: float
    energy_err_mean_pct: float | None
    energy_err_max_pct: float | None
    calib_T: float
    calib_dP: float


def postprocess(df: pd.DataFrame, fluid: Fluid, solid: Solid, spec: PlateSpec) -> tuple[pd.DataFrame, PostSummary]:
    rows = []
    for r in df.itertuples(index=False):
        ch = make_channels(r.w_mm, r.t_mm, r.H_mm, spec)
        m = thermal_model(ch, r.flow_lpm, r.Q_W, r.T_in_C, fluid, solid, spec)
        V = lpm_to_m3s(r.flow_lpm)
        R_th = (r.T_max_cfd - r.T_in_C) / r.Q_W
        out = dict(run=r.run, N=ch.N, Dh_mm=ch.Dh * 1e3, aspect=ch.aspect, Re=m.Re, v_ms=m.v,
                   R_th_cfd=R_th, R_th_model=m.R_th, T_max_model=m.T_max, dP_model=m.dP_total,
                   pump_mW_cfd=r.dP_cfd * V * 1e3, err_T=r.T_max_cfd - m.T_max,
                   err_dP_pct=(r.dP_cfd - m.dP_total) / m.dP_total * 100, Nu_model=m.Nu)
        # neraca energi
        T_out = getattr(r, "T_out_cfd", np.nan)
        if T_out is not None and not pd.isna(T_out):
            q_w = fluid.rho * V * fluid.cp * (T_out - r.T_in_C)
            out["energy_err_pct"] = (q_w - r.Q_W) / r.Q_W * 100
        # Nu efektif dari CFD
        R_conv = R_th - m.R_cond - m.R_heat
        if R_conv > 0:
            h_eff = h_from_R_conv(R_conv, ch, solid)
            out["h_eff"] = h_eff
            out["Nu_eff_cfd"] = h_eff * ch.Dh / fluid.k
        # faktor gesek semu dari dP kanal
        dPc = getattr(r, "dP_channel_cfd", np.nan)
        if dPc is not None and not pd.isna(dPc):
            out["fRe_app_cfd"] = dPc * ch.Dh / (2 * ch.L * fluid.rho * m.v**2) * m.Re
            out["fRe_app_model"] = m.fRe_app
        rows.append(out)
    res = df.merge(pd.DataFrame(rows), on="run")
    e = res.get("energy_err_pct")
    summ = PostSummary(
        n_runs=len(res),
        T_mae_model=float(np.mean(np.abs(res.err_T))),
        T_bias_model=float(np.mean(res.err_T)),
        dP_mape_model=float(np.mean(np.abs(res.err_dP_pct))),
        energy_err_mean_pct=None if e is None else float(np.nanmean(np.abs(e))),
        energy_err_max_pct=None if e is None else float(np.nanmax(np.abs(e))),
        calib_T=float(np.mean((res.T_max_cfd - res.T_in_C) / (res.T_max_model - res.T_in_C))),
        calib_dP=float(np.mean(res.dP_cfd / res.dP_model)),
    )
    return res, summ
