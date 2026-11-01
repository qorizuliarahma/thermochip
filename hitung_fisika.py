"""
Menghitung prediksi model fisika untuk SATU kasus, untuk mengisi kolom "fisika" di Tabel 4.6 proposal.

Contoh:
    python hitung_fisika.py --w 1.0 --t 0.5 --H 3.0 --flow 1.0 --material al6061
    python hitung_fisika.py --w 1.0 --t 0.5 --H 3.0 --v-port 0.8 --material silicon --air autodesk

--air autodesk memakai properti Water bawaan Autodesk CFD (μ 1,003 mPa·s, k 0,6 W/m·K,
cp 4.182 J/kg·K, ρ 998,2 kg/m³) agar perbandingan dengan CFD adil.
"""
from __future__ import annotations

import argparse
import math

from tc.correlations import thermal_model
from tc.geometry import PlateSpec, make_channels
from tc.properties import AL6061, COPPER, SILICON, WATER_25C, WATER_AUTODESK, Solid

SOLID = {"al6061": AL6061, "aluminium": Solid("Aluminum (pustaka Autodesk CFD)", k=204.0, rho=2707.0), "copper": COPPER, "silicon": SILICON}
AIR = {"konstan": WATER_25C, "autodesk": WATER_AUTODESK}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=float, required=True, help="lebar kanal (mm)")
    ap.add_argument("--t", type=float, required=True, help="tebal sirip (mm)")
    ap.add_argument("--H", type=float, required=True, help="tinggi kanal (mm)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--flow", type=float, help="laju aliran (L/menit)")
    g.add_argument("--v-port", type=float, help="kecepatan inlet di port (m/s)")
    ap.add_argument("--d-port", type=float, default=6.0, help="diameter port (mm)")
    ap.add_argument("--Q", type=float, default=300.0, help="daya chip (W)")
    ap.add_argument("--T-in", type=float, default=25.0)
    ap.add_argument("--material", default="al6061", choices=list(SOLID))
    ap.add_argument("--air", default="konstan", choices=list(AIR))
    a = ap.parse_args()

    flow = a.flow if a.flow is not None else a.v_port * math.pi * (a.d_port * 1e-3) ** 2 / 4 * 60000
    sp, fl, so = PlateSpec(), AIR[a.air], SOLID[a.material]
    ch = make_channels(a.w, a.t, a.H, sp)
    m = thermal_model(ch, flow, a.Q, a.T_in, fl, so, sp)
    mdot = fl.rho * flow / 60000
    print(f"Kasus: w={a.w} t={a.t} H={a.H} mm, N={ch.N}, {so.name}, {fl.name}")
    print(f"  laju aliran            : {flow:.3f} L/menit ({mdot * 1000:.2f} g/s)")
    print(f"  bilangan Reynolds kanal: {m.Re:.0f}")
    print(f"  T maks chip (fisika)   : {m.T_max:.1f} °C")
    print(f"  pressure drop total    : {m.dP_total:.0f} Pa (kanal {m.dP_channel:.0f} Pa)")
    print(f"  hambatan termal        : {m.R_th:.4f} °C/W")
    print(f"  T keluar seharusnya    : {a.T_in + a.Q / (mdot * fl.cp):.2f} °C  (cek terhadap bulk temperature CFD)")


if __name__ == "__main__":
    main()
