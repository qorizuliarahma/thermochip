"""
Geometri cold plate kanal lurus paralel.

Konvensi (satuan SI di dalam kode, mm hanya di file CSV):
  w  lebar kanal, t tebal sirip, H tinggi kanal, L panjang kanal,
  W_reg lebar area kanal, N = floor(W_reg / (w + t)).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PlateSpec:
    """Dimensi yang tetap di semua run. Samakan dengan model CAD Anda."""
    region_width: float = 40e-3     # m, lebar area kanal
    channel_length: float = 40e-3   # m, panjang aliran di kanal
    base_thickness: float = 2e-3    # m, tebal base di bawah kanal
    die_size: float = 30e-3         # m, sisi die (persegi)
    die_thickness: float = 1e-3     # m
    port_diameter: float = 6e-3     # m


@dataclass(frozen=True)
class Channels:
    w: float
    t: float
    H: float
    N: int
    L: float

    @property
    def area(self) -> float:            # luas penampang satu kanal
        return self.w * self.H

    @property
    def perimeter(self) -> float:
        return 2.0 * (self.w + self.H)

    @property
    def Dh(self) -> float:              # diameter hidraulik, 4A/P
        return 4.0 * self.area / self.perimeter

    @property
    def alpha(self) -> float:           # rasio sisi pendek/panjang (0 < alpha <= 1)
        return min(self.w, self.H) / max(self.w, self.H)

    @property
    def aspect(self) -> float:          # rasio tinggi/lebar (untuk kendala fabrikasi)
        return self.H / self.w


def make_channels(w_mm: float, t_mm: float, H_mm: float, spec: PlateSpec) -> Channels:
    w, t, H = w_mm * 1e-3, t_mm * 1e-3, H_mm * 1e-3
    N = int(math.floor(spec.region_width / (w + t) + 1e-9))
    if N < 1:
        raise ValueError("Lebar kanal + sirip melebihi area kanal.")
    return Channels(w=w, t=t, H=H, N=N, L=spec.channel_length)


def lpm_to_m3s(q_lpm: float) -> float:
    return q_lpm / 60000.0
