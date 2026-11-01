"""
ThermoChip - alur integrasi CFD dan machine learning (ML).

Contoh pemakaian (jalankan dari folder ini):
    python run_analysis.py --demo                  # uji alur dengan data sintetis (BUKAN hasil riset)
    python run_analysis.py                         # pakai data/cfd_results.csv dan data/mesh_study.csv
    python run_analysis.py --solid copper --dp-max 800 --w-min 0.5 --ar-max 8

Langkah:
  1. Uji independensi mesh (GCI, Celik et al. 2008)
  2. Pengolahan CFD: neraca energi, hambatan termal, Nu dan f efektif vs korelasi
  3. Model ML: GP, GBR, dan Fisika+GP, dibandingkan dengan repeated k-fold CV
  4. Penjelasan SHAP untuk model terbaik
  5. Optimasi berkendala dan front Pareto
  6. Sampling adaptif: usulan kasus CFD berikutnya (Expected Improvement, Jones dkk. 1998)
  7. Analisis tekno-ekonomi per rak AI
Semua tabel (CSV) dan gambar (PNG 300 dpi) disimpan di folder results/ (atau results_demo/).
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from tc.cfd_post import load_cfd, postprocess
from tc.correlations import thermal_model_vec
from tc.gci import gci, representative_h
from tc.geometry import PlateSpec, make_channels
from tc.optimize import FabLimits, optimize, pareto_sweep
from tc.plots import energy_balance, parity, pareto, shap_summary, theory_vs_cfd
from tc.properties import FLUIDS, SOLIDS, WATER_25C
from tc.adaptive import suggest_runs
from tc.surrogate import FEATURES, PhysicsResidual, candidates, cross_validate, shap_values
from tc import tekno_ekonomi as tea

ROOT = Path(__file__).parent
BOUNDS = {"w_mm": (0.5, 1.5), "t_mm": (0.3, 1.0), "H_mm": (2.0, 5.0), "flow_lpm": (0.5, 2.0)}


def physics_fns(solid, spec, Q=300.0, T_in=25.0, fluid=WATER_25C):
    """Model fisika (vektor) sebagai fungsi DataFrame -> array, untuk model hibrid Fisika+GP."""
    def T(X):
        return thermal_model_vec(X.w_mm, X.t_mm, X.H_mm, X.flow_lpm, Q, T_in, fluid, solid, spec)[0]

    def logdP(X):
        return np.log10(thermal_model_vec(X.w_mm, X.t_mm, X.H_mm, X.flow_lpm, Q, T_in, fluid, solid, spec)[1])
    return T, logdP


def step_mesh(path: Path, out: Path):
    if not path.exists():
        print("  (lewati) data mesh tidak ada:", path)
        return None
    m = pd.read_csv(path)
    rows = []
    m = m.dropna(subset=["n_cells", "total_volume_m3", "value"])
    if m.empty:
        print("  (lewati) data mesh belum diisi")
        return None
    for q, g in m.groupby("quantity"):
        g = g.assign(h=[representative_h(n, v) for n, v in zip(g.n_cells, g.total_volume_m3)]).sort_values("h")
        if len(g) < 3:
            continue
        r = gci(*g.value.iloc[:3], *g.h.iloc[:3])
        rows.append(dict(quantity=q, phi_fine=r.phi1, phi_medium=r.phi2, phi_coarse=r.phi3, r21=r.r21,
                         r32=r.r32, p=r.p, phi_extrapolated=r.phi_ext, e_a21_pct=100 * r.e_a21,
                         GCI_fine_pct=100 * r.gci_fine21, oscillatory=r.oscillatory, note=r.note))
    t = pd.DataFrame(rows)
    t.to_csv(out / "tabel_gci.csv", index=False)
    print(t[["quantity", "p", "GCI_fine_pct"]].round(3).to_string(index=False))
    return t


def step_tea(out: Path):
    print("\n6) Analisis tekno-ekonomi per rak AI")
    asm = tea.Asumsi()
    tea.tabel_energi(asm).to_csv(out / "tabel_tea_energi.csv", index=False)
    tea.tabel_sensitivitas(asm).to_csv(out / "tabel_tea_sensitivitas.csv")
    pb = tea.tabel_payback(asm); pb.to_csv(out / "tabel_tea_payback.csv", index=False)
    print(pb.to_string(index=False))


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="pakai data sintetis untuk menguji alur")
    ap.add_argument("--solid", default="al6061", choices=list(SOLIDS))
    ap.add_argument("--air", default="autodesk", choices=list(FLUIDS), help="properti air model fisika (autodesk = sama dengan CFD)")
    ap.add_argument("--dp-max", type=float, default=800.0, help="batas pressure drop (Pa)")
    ap.add_argument("--w-min", type=float, default=0.5, help="lebar kanal minimum fabrikasi (mm)")
    ap.add_argument("--t-min", type=float, default=0.3, help="tebal sirip minimum fabrikasi (mm)")
    ap.add_argument("--ar-max", type=float, default=10.0, help="rasio H/w maksimum fabrikasi")
    ap.add_argument("--min-ml", type=int, default=15, help="jumlah run CFD minimum sebelum model ML dilatih")
    ap.add_argument("--n-adaptif", type=int, default=10, help="jumlah kasus CFD tambahan yang diusulkan")
    a = ap.parse_args()

    spec, solid, fluid = PlateSpec(), SOLIDS[a.solid], FLUIDS[a.air]
    if a.demo:
        from make_demo_data import make_demo
        data_dir, out = ROOT / "data_demo", ROOT / "results_demo"
        make_demo(data_dir, solid, spec)
        print("MODE DEMO: data sintetis, jangan dipakai sebagai hasil riset.\n")
    else:
        data_dir, out = ROOT / "data", ROOT / "results"
    out.mkdir(exist_ok=True)

    print("1) Uji independensi mesh (GCI)")
    step_mesh(data_dir / "mesh_study.csv", out)

    print("\n2) Pengolahan hasil CFD")
    try:
        df = load_cfd(data_dir / "cfd_results.csv")
    except ValueError as e:
        print("  " + str(e) + " Isi hasil CFD di data/lembar_running_CFD.xlsx, jalankan python xlsx_ke_csv.py, lalu ulangi.")
        step_tea(out)
        return
    res, s = postprocess(df, fluid, solid, spec)
    res.to_csv(out / "tabel_cfd_terolah.csv", index=False)
    print(f"  {s.n_runs} run | model fisika vs CFD: MAE T_maks {s.T_mae_model:.2f} C (bias {s.T_bias_model:+.2f}),"
          f" MAPE dP {s.dP_mape_model:.1f}%")
    if s.energy_err_mean_pct is not None:
        print(f"  neraca energi: rata-rata |galat| {s.energy_err_mean_pct:.2f}%, maks {s.energy_err_max_pct:.2f}%")
        energy_balance(res, out / "gambar_neraca_energi.png")
    theory_vs_cfd(res, out / "gambar_teori_vs_cfd.png")

    if s.n_runs < a.min_ml:
        print(f"\n3–5) Model ML, optimasi, dan sampling adaptif DILEWATI: baru {s.n_runs} run CFD "
              f"(minimal {a.min_ml}). Lanjutkan simulasi lalu jalankan ulang.")
        step_tea(out)
        print(f"\nSelesai. Hasil di: {out}")
        return

    print("\n3) Model ML (repeated 5-fold CV)")
    X = res[FEATURES].reset_index(drop=True)
    pT, pP = physics_fns(solid, spec, fluid=fluid)
    best, scores_all = {}, []
    for target, y, back, phys, unit, name in [
        ("T_max", res.T_max_cfd.values, lambda v: v, pT, "°C", "T maks"),
        ("dP", np.log10(res.dP_cfd.values), lambda v: 10 ** v, pP, "Pa", "ΔP"),
    ]:
        models = candidates(phys)
        scores, oof = cross_validate(models, X, y, target, back=back)
        scores_all += [vars(sc) for sc in scores]
        win = min(scores, key=lambda sc: sc.RMSE).model
        print("  " + target + ": " + ", ".join(f"{sc.model} RMSE={sc.RMSE:.3g}" for sc in scores) + f"  -> {win}")
        best[target] = models[win].fit(X, y)
        parity(back(y), oof[win], name, unit, out / f"gambar_parity_{target}.png", title=f"Validasi silang: {win}")
        predict = (lambda X_, m=best[target], b=back: b(m.predict(X_)))
        expl = shap_values(predict, X)
        shap_summary(expl, out / f"gambar_shap_{target}.png", f"Pengaruh parameter terhadap {name} (SHAP, {win})")
    pd.DataFrame(scores_all).to_csv(out / "tabel_cv_model.csv", index=False)

    print("\n4) Optimasi berkendala")
    fT = lambda X_: best["T_max"].predict(X_)
    fP = lambda X_: 10 ** best["dP"].predict(X_)
    fab = FabLimits(a.w_min, a.t_min, a.ar_max)
    opt = optimize(fT, fP, BOUNDS, a.dp_max, fab)
    print("  desain terbaik:", {k: round(v, 3) if isinstance(v, float) else v for k, v in opt.items()})
    front = pareto_sweep(fT, fP, BOUNDS, fab, np.geomspace(res.dP_cfd.min(), res.dP_cfd.max(), 10))
    front.to_csv(out / "tabel_pareto.csv", index=False)
    pareto(front, res, out / "gambar_pareto.png")
    print("\n5) Sampling adaptif: usulan kasus CFD berikutnya")
    hyb = PhysicsResidual(pT).fit(X, res.T_max_cfd.values)
    usul, best_T = suggest_runs(hyb, fP, X, res.T_max_cfd.values, BOUNDS, a.dp_max, fab, n_new=a.n_adaptif)
    usul.to_csv(out / "tabel_usulan_cfd_adaptif.csv", index=False)
    print(f"  T maks terbaik saat ini (dP <= {a.dp_max:.0f} Pa): {best_T:.2f} C")
    print(usul[["run"] + FEATURES + ["T_pred", "T_std", "dP_pred"]].to_string(index=False))
    print("  -> simulasikan run A01.. di Autodesk CFD, tambahkan ke cfd_results.csv, lalu jalankan ulang.")

    step_tea(out)

    (out / "ringkasan.json").write_text(json.dumps(dict(postprocess=vars(s), cv=scores_all, optimum=opt),
                                                   indent=2, default=float))
    print(f"\nSelesai. Hasil di: {out}")


if __name__ == "__main__":
    main()
