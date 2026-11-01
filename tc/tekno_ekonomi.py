"""
Analisis tekno-ekonomi orde besaran per rak AI (mereproduksi Tabel 5.1-5.3 proposal).

    E_hemat = P_chiller * f * 8760 jam;  S = E_hemat * tarif           (Persamaan 3.4)
    Periode pengembalian = C / S                                          (Persamaan 3.5)
    NPV = -C + sum_{k=1..n} S / (1 + i)^k                                 (Persamaan 3.6)

Asumsi (ubah sesuai data operator):
  P_TI rak 140 kW (TrendForce, 2024); pendinginan 50% dari TI (David dkk., 2012);
  kompresor chiller 50% dari pendinginan (Iyengar & Schmidt, 2010);
  tarif PLN B-3/TM Rp1.122/kWh (Setiawan, 2026).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Asumsi:
    P_TI_kW: float = 140.0
    frac_cooling: float = 0.50
    frac_compressor: float = 0.50
    tarif: float = 1122.0          # Rp/kWh
    i: float = 0.08
    n_tahun: int = 5

    @property
    def P_chiller_kW(self):
        return self.P_TI_kW * self.frac_cooling * self.frac_compressor


def hemat(a: Asumsi, f: float, tarif: float | None = None):
    E = a.P_chiller_kW * f * 8760 / 1000          # MWh/tahun
    return E, E * 1000 * (tarif or a.tarif) / 1e6  # juta Rp/tahun


def npv(C, S, i, n):
    return -C + S * (1 - (1 + i) ** -n) / i


def tabel_energi(a: Asumsi):
    rows = [("Daya TI rak (kW)", a.P_TI_kW), ("Daya pendinginan (kW)", a.P_TI_kW * a.frac_cooling),
            ("Daya kompresor chiller (kW)", a.P_chiller_kW)]
    for f in (0.5, 1.0):
        E, S = hemat(a, f)
        rows += [(f"Penghematan f={f:.0%} (MWh/tahun)", round(E, 1)), (f"Nilai f={f:.0%} (juta Rp/tahun)", round(S))]
    return pd.DataFrame(rows, columns=["besaran", "nilai"])


def tabel_sensitivitas(a: Asumsi, fs=(0.25, 0.5, 0.75, 1.0), dtarif=(-0.2, 0.0, 0.2)):
    return pd.DataFrame({f"f={f:.0%}": [round(hemat(a, f, a.tarif * (1 + d))[1]) for d in dtarif] for f in fs},
                        index=[f"Rp{a.tarif * (1 + d):,.0f}/kWh" for d in dtarif])


def tabel_payback(a: Asumsi, investasi=(250, 500, 1000), fs=(0.5, 1.0)):
    rows = []
    for C in investasi:
        r = {"investasi (juta Rp)": C}
        for f in fs:
            S = hemat(a, f)[1]
            r[f"pengembalian f={f:.0%} (tahun)"] = round(C / S, 1)
            r[f"NPV f={f:.0%} (juta Rp)"] = round(npv(C, S, a.i, a.n_tahun))
        rows.append(r)
    return pd.DataFrame(rows)


def biaya_toleransi(a: Asumsi, f=0.5, tahun=3.0, n_gpu=72):
    """Investasi maksimum per posisi GPU agar balik modal dalam `tahun` (juta Rp)."""
    return hemat(a, f)[1] * tahun / n_gpu


if __name__ == "__main__":
    a = Asumsi()
    print(tabel_energi(a).to_string(index=False), "\n")
    print(tabel_sensitivitas(a), "\n")
    print(tabel_payback(a).to_string(index=False), "\n")
    print(f"Biaya tambahan yang dapat ditoleransi: Rp{biaya_toleransi(a):.1f} juta per posisi GPU (balik modal 3 tahun)")
