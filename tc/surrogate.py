"""
Model surrogate (ML) dari data CFD dengan validasi silang dan pemilihan model.

Tiga kandidat dibandingkan secara adil dengan repeated k-fold cross-validation:
  1. GP        : Gaussian Process, kernel Matern 5/2 + ARD + derau (cocok untuk data CFD kecil)
  2. GBR       : Gradient Boosting Regression (Friedman, 2001, doi:10.1214/aos/1013203451)
  3. Fisika+GP : physics-informed residual learning, y = model_fisika(x) + GP(x).
                 GP hanya mempelajari selisih CFD terhadap teori [TP81], sehingga
                 ekstrapolasi tetap mengikuti fisika dan data sedikit sudah cukup.

Target: T_max_cfd (degC) dan log10(dP_cfd) (karena dP bervariasi > 1 orde besaran).
Penjelasan: SHAP (Lundberg et al., 2020, Nat. Mach. Intell. 2, 56-67,
            doi:10.1038/s42256-019-0138-9; Lundberg & Lee, 2017, arXiv:1705.07874).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RepeatedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["w_mm", "t_mm", "H_mm", "flow_lpm"]
LABELS = {"w_mm": "Lebar kanal w (mm)", "t_mm": "Tebal sirip t (mm)",
          "H_mm": "Tinggi kanal H (mm)", "flow_lpm": "Laju aliran (L/menit)"}


def _gp() -> GaussianProcessRegressor:
    k = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=np.ones(4), length_scale_bounds=(1e-2, 1e2), nu=2.5) \
        + WhiteKernel(1e-3, (1e-8, 1e0))
    return GaussianProcessRegressor(kernel=k, normalize_y=True, n_restarts_optimizer=2, random_state=0)


class PhysicsResidual(BaseEstimator, RegressorMixin):
    """y = f_fisika(x) + GP(x). f_fisika diberikan sebagai fungsi DataFrame -> array."""

    def __init__(self, physics: Callable[[pd.DataFrame], np.ndarray] | None = None):
        self.physics = physics

    def fit(self, X, y):
        X = pd.DataFrame(X, columns=FEATURES)
        self.model_ = make_pipeline(StandardScaler(), _gp())
        self.model_.fit(X, np.asarray(y) - self.physics(X))
        return self

    def predict(self, X, return_std=False):
        X = pd.DataFrame(X, columns=FEATURES)
        if return_std:
            m, sd = self.model_.predict(X, return_std=True)
            return self.physics(X) + m, sd
        return self.physics(X) + self.model_.predict(X)


def candidates(physics_fn) -> dict:
    return {
        "GP": make_pipeline(StandardScaler(), _gp()),
        "GBR": GradientBoostingRegressor(n_estimators=400, max_depth=2, learning_rate=0.05,
                                         subsample=0.8, random_state=0),
        "Fisika+GP": PhysicsResidual(physics_fn),
    }


@dataclass
class CVScore:
    model: str
    target: str
    R2: float
    MAE: float
    RMSE: float


def cross_validate(models: dict, X: pd.DataFrame, y: np.ndarray, target: str,
                   n_splits: int = 5, n_repeats: int = 3, back=lambda v: v):
    """Repeated k-fold CV. Metrik dihitung pada skala asli (back mengubah log10 -> Pa)."""
    scores, oof = [], {}
    k = min(n_splits, len(X))
    for name, est in models.items():
        preds = np.zeros((n_repeats, len(X)))
        for i, (tr, te) in enumerate(RepeatedKFold(n_splits=k, n_repeats=n_repeats, random_state=0).split(X)):
            m = clone(est).fit(X.iloc[tr], y[tr])
            preds[i // k, te] = m.predict(X.iloc[te])
        p = back(preds.mean(axis=0))
        t = back(y)
        oof[name] = p
        scores.append(CVScore(name, target, r2_score(t, p), mean_absolute_error(t, p),
                              float(np.sqrt(mean_squared_error(t, p)))))
    return scores, oof


def shap_values(predict_fn, X: pd.DataFrame, n_background: int = 20):
    """SHAP model-agnostik (Permutation explainer) — berlaku untuk GP, GBR, maupun hibrid."""
    import shap
    bg = shap.sample(X, min(n_background, len(X)), random_state=0)
    explainer = shap.Explainer(lambda a: predict_fn(pd.DataFrame(a, columns=FEATURES)), bg,
                               algorithm="permutation")
    return explainer(X)
