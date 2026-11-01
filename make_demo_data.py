"""
Pembuat data DEMO (sintetis) untuk menguji alur analisis sebelum hasil CFD tersedia.

Data dibuat dari model fisika ditambah bias dan derau buatan agar menyerupai perilaku CFD.
JANGAN dipakai sebagai hasil penelitian atau dimasukkan ke proposal.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

from tc.correlations import thermal_model
from tc.geometry import PlateSpec, make_channels
from tc.properties import WATER_25C


def make_demo(folder: Path, solid, spec: PlateSpec, n: int = 50, seed: int = 2026):
    folder.mkdir(exist_ok=True)
    rng = np.random.default_rng(seed)
    lo, hi = np.array([0.5, 0.3, 2.0, 0.5]), np.array([1.5, 1.0, 5.0, 2.0])
    X = qmc.scale(qmc.LatinHypercube(d=4, seed=seed).random(n), lo, hi).round(2)
    rows = []
    for i, (w, t, H, q) in enumerate(X, 1):
        ch = make_channels(w, t, H, spec)
        m = thermal_model(ch, q, 300.0, 25.0, WATER_25C, solid, spec, spreading_factor=0.85, K_minor_port=3.0)
        rows.append(dict(run=f"R{i:02d}", w_mm=w, t_mm=t, H_mm=H, flow_lpm=q, Q_W=300, T_in_C=25,
                         T_max_cfd=m.T_max + rng.normal(0, 0.3),
                         dP_cfd=m.dP_total * (1 + rng.normal(0, 0.03)),
                         T_out_cfd=m.T_out * 0 + 25 + (m.T_out - 25) * (1 + rng.normal(0, 0.01)),
                         dP_channel_cfd=m.dP_channel * (1 + rng.normal(0, 0.03)),
                         mesh_elements=int(rng.integers(8e5, 1.6e6))))
    pd.DataFrame(rows).to_csv(folder / "cfd_results.csv", index=False)
    vol = 60e-3 * 60e-3 * 9e-3
    mesh = []
    for qn, f, exact in [("T_max", lambda h: 55.2 + 1.0e6 * h**2, 55.2), ("dP", lambda h: 610 + 4.0e7 * h**2, 610)]:
        for lvl, nc in [("halus", 1_600_000), ("sedang", 700_000), ("kasar", 300_000)]:
            h = (vol / nc) ** (1 / 3)
            mesh.append(dict(quantity=qn, mesh=lvl, n_cells=nc, total_volume_m3=vol, value=round(f(h), 4)))
    pd.DataFrame(mesh).to_csv(folder / "mesh_study.csv", index=False)
