"""
Memindahkan hasil Autodesk CFD dari data/lembar_running_CFD.xlsx ke CSV yang dibaca run_analysis.py.

    python xlsx_ke_csv.py                 # kasus aluminium 300 W -> data/cfd_results.csv
    python xlsx_ke_csv.py --material Tembaga --q 1000 --out data/cfd_results_tembaga.csv

Hanya kasus dengan material dan daya yang sama dipakai bersama untuk melatih model ML,
karena model fisika di dalam model hibrid memakai satu material dan satu daya chip.
Uji mesh di sheet Mesh_GCI ditulis ke data/mesh_study.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
COLS = {"Run": "run", "w (mm)": "w_mm", "t (mm)": "t_mm", "H (mm)": "H_mm", "Laju aliran (L/menit)": "flow_lpm",
        "Q (W)": "Q_W", "T_in (°C)": "T_in_C", "T_max_cfd (°C)": "T_max_cfd", "dP_cfd (Pa)": "dP_cfd",
        "T_out_cfd (°C)": "T_out_cfd", "dP_channel_cfd (Pa)": "dP_channel_cfd", "mesh_elements": "mesh_elements"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "lembar_running_CFD.xlsx"))
    ap.add_argument("--material", default="Al 6061")
    ap.add_argument("--q", type=float, default=300.0)
    ap.add_argument("--out", default=str(ROOT / "data" / "cfd_results.csv"))
    a = ap.parse_args()

    k = pd.read_excel(a.xlsx, sheet_name="Kasus", header=6)
    k = k[k["Run"].astype(str).str.match(r"^(CP-\d|R\d)")]
    sel = k[(k["Material"] == a.material) & (k["Q (W)"] == a.q)]
    out = sel[list(COLS)].rename(columns=COLS)
    out.to_csv(a.out, index=False)
    done = out["T_max_cfd"].notna() & out["dP_cfd"].notna()
    print(f"{a.out}: {len(out)} kasus, {int(done.sum())} sudah berisi hasil CFD")
    lain = k[~k.index.isin(sel.index) & k["T_max_cfd (°C)"].notna()]
    if len(lain):
        print("Catatan: kasus berikut beda material/daya dan tidak ikut:", ", ".join(lain["Run"]))

    m = pd.read_excel(a.xlsx, sheet_name="Mesh_GCI", header=5, nrows=6)
    vol = pd.read_excel(a.xlsx, sheet_name="Mesh_GCI", header=None).iloc[3, 1]
    mesh = pd.DataFrame({"quantity": m["Besaran"], "mesh": m["Mesh"], "n_cells": m["Jumlah elemen"],
                         "total_volume_m3": vol, "value": m["Nilai"]})
    mesh.to_csv(ROOT / "data" / "mesh_study.csv", index=False)
    print(f"data/mesh_study.csv: {int(mesh['value'].notna().sum())} dari 6 nilai terisi")


if __name__ == "__main__":
    main()
