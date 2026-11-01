"""Gambar siap pakai untuk proposal dan artikel (PNG 300 dpi, label bahasa Indonesia)."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .surrogate import LABELS

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
BLUE, RED, GREY, DARK = "#2f6fb3", "#c8553d", "#8a8a8a", "#1f2a44"


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def parity(y_true, y_pred, label, unit, path, title=None):
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.scatter(y_true, y_pred, s=18, color=BLUE, edgecolor="white", lw=0.4)
    lo, hi = min(np.min(y_true), np.min(y_pred)), max(np.max(y_true), np.max(y_pred))
    ax.plot([lo, hi], [lo, hi], color=GREY, lw=0.8)
    ax.set_xlabel(f"{label} CFD ({unit})")
    ax.set_ylabel(f"{label} prediksi ML ({unit})")
    if title:
        ax.set_title(title, fontsize=9)
    _save(fig, path)


def theory_vs_cfd(df: pd.DataFrame, path):
    """Nu efektif CFD vs Nu korelasi, dan fRe semu CFD vs korelasi Shah (bila tersedia)."""
    has_f = "fRe_app_cfd" in df and df["fRe_app_cfd"].notna().any()
    fig, axs = plt.subplots(1, 2 if has_f else 1, figsize=(7.0 if has_f else 3.6, 3.3))
    axs = np.atleast_1d(axs)
    ax = axs[0]
    ok = df["Nu_eff_cfd"].notna() if "Nu_eff_cfd" in df else []
    ax.scatter(df.loc[ok, "Re"], df.loc[ok, "Nu_eff_cfd"], s=18, color=BLUE, label="CFD (efektif)")
    ax.scatter(df.loc[ok, "Re"], df.loc[ok, "Nu_model"], s=18, color=RED, marker="x", label="Korelasi")
    ax.set_xlabel("Bilangan Reynolds"); ax.set_ylabel("Bilangan Nusselt")
    ax.set_title("(a) Perpindahan panas", fontsize=9); ax.legend(frameon=False, fontsize=7)
    if has_f:
        ax = axs[1]
        ok = df["fRe_app_cfd"].notna()
        ax.scatter(df.loc[ok, "Re"], df.loc[ok, "fRe_app_cfd"], s=18, color=BLUE, label="CFD")
        ax.scatter(df.loc[ok, "Re"], df.loc[ok, "fRe_app_model"], s=18, color=RED, marker="x", label="Shah (1978)")
        ax.set_xlabel("Bilangan Reynolds"); ax.set_ylabel("f$_{app}$ Re (Fanning)")
        ax.set_title("(b) Gesekan aliran", fontsize=9); ax.legend(frameon=False, fontsize=7)
    _save(fig, path)


def energy_balance(df: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    ax.bar(df["run"].astype(str), df["energy_err_pct"], color=[BLUE if abs(v) <= 2 else RED for v in df["energy_err_pct"]])
    ax.axhspan(-2, 2, color="#e7f1fb", zorder=0)
    ax.set_ylabel("Galat neraca energi (%)"); ax.set_xlabel("Run CFD")
    ax.tick_params(axis="x", rotation=90, labelsize=6)
    _save(fig, path)


def shap_summary(expl, path, title):
    import shap
    expl.feature_names = [LABELS[f] for f in expl.feature_names]
    plt.figure()
    shap.plots.beeswarm(expl, show=False, plot_size=(6.2, 3.2))
    plt.title(title, fontsize=9)
    plt.xlabel("Nilai SHAP (pengaruh terhadap prediksi)")
    plt.tight_layout(); plt.savefig(path, dpi=300); plt.close("all")


def pareto(front: pd.DataFrame, cfd: pd.DataFrame, path, baseline=None):
    fig, ax = plt.subplots(figsize=(5.6, 3.3))
    ax.scatter(cfd["dP_cfd"], cfd["T_max_cfd"], s=16, color="#c9d6e6", label="Run CFD")
    ax.plot(front["dP"], front["T_max"], "-o", color=DARK, ms=3, lw=1.2, label="Front Pareto (ML + kendala fabrikasi)")
    if baseline is not None:
        ax.scatter([baseline[1]], [baseline[0]], marker="s", s=40, color=GREY, label="Baseline", zorder=3)
    ax.set_xscale("log"); ax.set_xlabel("Pressure drop (Pa, skala log)"); ax.set_ylabel("T maks chip (°C)")
    from matplotlib.ticker import NullFormatter, ScalarFormatter
    ax.xaxis.set_major_formatter(ScalarFormatter()); ax.xaxis.set_minor_formatter(NullFormatter())
    ax.legend(frameon=False, fontsize=7)
    _save(fig, path)
