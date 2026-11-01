"""
Grid Convergence Index (GCI) untuk uji independensi mesh.

Prosedur mengikuti:
  Celik, I.B., Ghia, U., Roache, P.J. & Freitas, C.J. (2008). Procedure for estimation and
  reporting of uncertainty due to discretization in CFD applications.
  J. Fluids Eng. 130(7), 078001. doi:10.1115/1.2960953

Langkah:
  1. h = (V_total / N_sel)^(1/3)    (ukuran sel representatif 3D)
  2. tiga mesh: h1 < h2 < h3 (1 = paling halus), disarankan r = h_kasar/h_halus > 1.3
  3. orde semu p dari iterasi titik tetap
  4. nilai ekstrapolasi, galat relatif, dan GCI_halus = 1.25 e_a / (r^p - 1)
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class GCIResult:
    phi1: float
    phi2: float
    phi3: float
    r21: float
    r32: float
    p: float
    phi_ext: float
    e_a21: float
    e_ext21: float
    gci_fine21: float
    oscillatory: bool
    note: str = ""


def representative_h(n_cells: float, total_volume: float) -> float:
    return (total_volume / n_cells) ** (1.0 / 3.0)


def gci(phi1: float, phi2: float, phi3: float, h1: float, h2: float, h3: float,
        Fs: float = 1.25, max_iter: int = 200) -> GCIResult:
    if not (h1 < h2 < h3):
        raise ValueError("Urutkan mesh: h1 (halus) < h2 < h3 (kasar).")
    r21, r32 = h2 / h1, h3 / h2
    e21, e32 = phi2 - phi1, phi3 - phi2
    if abs(e21) < 1e-14 or abs(e32) < 1e-14:
        return GCIResult(phi1, phi2, phi3, r21, r32, float("nan"), phi1, 0.0, 0.0, 0.0, False,
                         "Selisih antar-mesh hampir nol: solusi sudah tidak bergantung mesh.")
    s = math.copysign(1.0, e32 / e21)
    p = abs(math.log(abs(e32 / e21))) / math.log(r21)
    for _ in range(max_iter):
        q = math.log((r21**p - s) / (r32**p - s))
        p_new = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(p_new - p) < 1e-10:
            p = p_new
            break
        p = p_new
    phi_ext = (r21**p * phi1 - phi2) / (r21**p - 1)
    e_a = abs((phi1 - phi2) / phi1)
    e_ext = abs((phi_ext - phi1) / phi_ext)
    gci_f = Fs * e_a / (r21**p - 1)
    note = ""
    if r21 < 1.3 or r32 < 1.3:
        note = "Rasio penghalusan < 1,3: disarankan menambah jumlah sel lebih besar antar-mesh."
    return GCIResult(phi1, phi2, phi3, r21, r32, p, phi_ext, e_a, e_ext, gci_f, s < 0, note)
