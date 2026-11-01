"""
Korelasi aliran laminar dan model hambatan termal cold plate.

Referensi utama:
  [TP81] Tuckerman, D.B. & Pease, R.F.W. (1981). High-performance heat sinking for VLSI.
         IEEE Electron Device Letters 2(5), 126-129. doi:10.1109/EDL.1981.25367
  [SL78] Shah, R.K. & London, A.L. (1978). Laminar Flow Forced Convection in Ducts.
         Academic Press. (kurva fRe dan Nu kanal persegi panjang)
  [S78]  Shah, R.K. (1978). A correlation for laminar hydrodynamic entry length solutions
         for circular and noncircular ducts. J. Fluids Eng. 100(2), 177-179.
         doi:10.1115/1.3448626
  [QM02] Qu, W. & Mudawar, I. (2002). Experimental and numerical study of pressure drop and
         heat transfer in a single-phase micro-channel heat sink. Int. J. Heat Mass Transfer
         45, 2549-2565. doi:10.1016/S0017-9310(01)00337-4  (pembanding validasi CFD)
  [IDB]  Incropera, DeWitt, Bergman & Lavine. Fundamentals of Heat and Mass Transfer
         (efisiensi sirip ujung adiabatik).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import Channels, PlateSpec, lpm_to_m3s
from .properties import Fluid, Solid, SILICON


# --------------------------------------------------------------------------- [SL78]
def fRe_fanning_fd(alpha: float) -> float:
    """Fanning f*Re aliran berkembang penuh, kanal persegi panjang (pendekatan polinomial [SL78])."""
    a = alpha
    return 24.0 * (1 - 1.3553*a + 1.9467*a**2 - 1.7012*a**3 + 0.9564*a**4 - 0.2537*a**5)


def Nu_H1_fd(alpha: float) -> float:
    """Nusselt berkembang penuh, kondisi batas H1 (fluks seragam aksial, temperatur keliling seragam) [SL78]."""
    a = alpha
    return 8.235 * (1 - 2.0421*a + 3.0853*a**2 - 2.4765*a**3 + 1.0578*a**4 - 0.1861*a**5)


def K_inf(alpha: float) -> float:
    """Koefisien penurunan tekanan tambahan daerah masuk, K(inf), kanal persegi panjang [SL78]."""
    a = alpha
    return 0.6796 + 1.2197*a + 3.3089*a**2 - 9.5921*a**3 + 8.9089*a**4 - 2.9959*a**5


def fRe_apparent_fanning(alpha: float, x_plus: float) -> float:
    """
    Faktor gesek semu (apparent) Fanning rata-rata dari inlet sampai x, bentuk korelasi Shah [S78]:
        f_app Re = 3.44/sqrt(x+) + [fRe_fd + K(inf)/(4x+) - 3.44/sqrt(x+)] / (1 + C/x+^2)
    dengan x+ = x/(Dh Re), C = 2.9e-4 untuk kanal persegi panjang.
    """
    s = 3.44 / math.sqrt(x_plus)
    return s + (fRe_fanning_fd(alpha) + K_inf(alpha) / (4 * x_plus) - s) / (1 + 2.9e-4 / x_plus**2)


def Nu_mean_developing(alpha: float, Gz: float) -> float:
    """Nusselt rata-rata dengan koreksi aliran termal berkembang bentuk Hausen, Gz = Dh Re Pr / L."""
    return Nu_H1_fd(alpha) + 0.0668 * Gz / (1 + 0.04 * Gz ** (2.0 / 3.0))


def fin_efficiency(h: float, k_s: float, t: float, H: float) -> float:
    """Sirip lurus ujung adiabatik [IDB]: eta = tanh(mH)/(mH), m = sqrt(2h/(k t))."""
    m = math.sqrt(2.0 * h / (k_s * t))
    return math.tanh(m * H) / (m * H)


# --------------------------------------------------------------------------- [TP81]
@dataclass
class ModelResult:
    N: int
    Re: float
    v: float
    Dh: float
    Nu: float
    h: float
    eta: float
    R_cond: float
    R_conv: float
    R_heat: float
    R_th: float
    T_max: float
    T_out: float
    dP_channel: float
    dP_total: float
    pump_W: float
    fRe_app: float


def thermal_model(ch: Channels, q_lpm: float, Q: float, T_in: float, fluid: Fluid, solid: Solid,
                  spec: PlateSpec, K_minor_channel: float = 1.0, K_minor_port: float = 2.5,
                  spreading_factor: float = 0.85) -> ModelResult:
    """
    Model jaringan hambatan termal [TP81]:
        T_max = T_in + Q (R_cond + R_conv + R_heat)
        R_cond = t_b/(k_s A_die) + t_die/(k_Si A_die)
        R_conv = 1 / (h N L (w + 2 eta H) * spreading_factor)
        R_heat = 1 / (rho cp V)
    Pressure drop = gesekan semu kanal [S78] + kerugian minor (mulut kanal & port).
    spreading_factor < 1 bila die lebih kecil dari area kanal (kalibrasi dari CFD).
    """
    V = lpm_to_m3s(q_lpm)
    v = V / (ch.N * ch.area)
    Re = fluid.rho * v * ch.Dh / fluid.mu
    x_plus = ch.L / (ch.Dh * Re)
    fRe_app = fRe_apparent_fanning(ch.alpha, x_plus)
    dP_ch = 4 * fRe_app / Re * (ch.L / ch.Dh) * 0.5 * fluid.rho * v**2
    v_port = V / (math.pi * spec.port_diameter**2 / 4)
    dP_tot = dP_ch + K_minor_channel * 0.5 * fluid.rho * v**2 + K_minor_port * 0.5 * fluid.rho * v_port**2

    Gz = ch.Dh * Re * fluid.Pr / ch.L
    Nu = Nu_mean_developing(ch.alpha, Gz)
    h = Nu * fluid.k / ch.Dh
    eta = fin_efficiency(h, solid.k, ch.t, ch.H)
    A_die = spec.die_size**2
    R_cond = spec.base_thickness / (solid.k * A_die) + spec.die_thickness / (SILICON.k * A_die)
    R_conv = 1.0 / (h * ch.N * ch.L * (ch.w + 2 * eta * ch.H) * spreading_factor)
    R_heat = 1.0 / (fluid.rho * fluid.cp * V)
    R_th = R_cond + R_conv + R_heat
    return ModelResult(N=ch.N, Re=Re, v=v, Dh=ch.Dh, Nu=Nu, h=h, eta=eta, R_cond=R_cond, R_conv=R_conv,
                       R_heat=R_heat, R_th=R_th, T_max=T_in + Q * R_th, T_out=T_in + Q * R_heat,
                       dP_channel=dP_ch, dP_total=dP_tot, pump_W=dP_tot * V, fRe_app=fRe_app)


def h_from_R_conv(R_conv: float, ch: Channels, solid: Solid, spreading_factor: float = 0.85) -> float:
    """
    Balik model: cari h sehingga 1/(h N L (w + 2 eta(h) H) phi) = R_conv.
    Dipakai untuk mengubah hasil CFD menjadi koefisien konveksi EFEKTIF (termasuk efek sebaran panas).
    """
    from scipy.optimize import brentq

    def g(h):
        eta = fin_efficiency(h, solid.k, ch.t, ch.H)
        return 1.0 / (h * ch.N * ch.L * (ch.w + 2 * eta * ch.H) * spreading_factor) - R_conv
    return brentq(g, 1.0, 1e7)


# --------------------------------------------------------------------------- versi vektor (cepat)
def thermal_model_vec(w_mm, t_mm, H_mm, q_lpm, Q, T_in, fluid: Fluid, solid: Solid, spec: PlateSpec,
                      K_minor_channel: float = 1.0, K_minor_port: float = 2.5, spreading_factor: float = 0.85):
    """Persamaan sama dengan thermal_model, dihitung untuk banyak desain sekaligus (numpy).
    Dipakai oleh model hibrid Fisika+GP dan optimasi. Mengembalikan (T_max, dP_total)."""
    import numpy as np
    w, t, H = np.asarray(w_mm) * 1e-3, np.asarray(t_mm) * 1e-3, np.asarray(H_mm) * 1e-3
    V = np.asarray(q_lpm) / 60000.0
    N = np.floor(spec.region_width / (w + t) + 1e-9)
    L = spec.channel_length
    A = w * H
    Dh = 4 * A / (2 * (w + H))
    a = np.minimum(w, H) / np.maximum(w, H)
    v = V / (N * A)
    Re = fluid.rho * v * Dh / fluid.mu
    xp = L / (Dh * Re)
    fre_fd = 24.0 * (1 - 1.3553*a + 1.9467*a**2 - 1.7012*a**3 + 0.9564*a**4 - 0.2537*a**5)
    kinf = 0.6796 + 1.2197*a + 3.3089*a**2 - 9.5921*a**3 + 8.9089*a**4 - 2.9959*a**5
    s = 3.44 / np.sqrt(xp)
    fre_app = s + (fre_fd + kinf / (4 * xp) - s) / (1 + 2.9e-4 / xp**2)
    v_port = V / (np.pi * spec.port_diameter**2 / 4)
    dP = 4 * fre_app / Re * (L / Dh) * 0.5 * fluid.rho * v**2 \
        + K_minor_channel * 0.5 * fluid.rho * v**2 + K_minor_port * 0.5 * fluid.rho * v_port**2
    Gz = Dh * Re * fluid.Pr / L
    nu_fd = 8.235 * (1 - 2.0421*a + 3.0853*a**2 - 2.4765*a**3 + 1.0578*a**4 - 0.1861*a**5)
    h = (nu_fd + 0.0668 * Gz / (1 + 0.04 * Gz ** (2 / 3))) * fluid.k / Dh
    m = np.sqrt(2 * h / (solid.k * t))
    eta = np.tanh(m * H) / (m * H)
    A_die = spec.die_size**2
    R = spec.base_thickness / (solid.k * A_die) + spec.die_thickness / (SILICON.k * A_die) \
        + 1 / (h * N * L * (w + 2 * eta * H) * spreading_factor) + 1 / (fluid.rho * fluid.cp * V)
    return T_in + Q * R, dP
