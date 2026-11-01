"""
Properti termofisik material dan fluida.

Nilai dipakai konstan (pada sekitar 25 degC). Kenaikan temperatur air di cold plate
hanya 2-9 degC, sehingga variasi properti air dapat diabaikan pada tahap ini.

Sumber:
  Air      : viskositas  - Huber et al. (2009), J. Phys. Chem. Ref. Data 38(2), 101-125,
                           doi:10.1063/1.3088050
             konduktivitas - Huber et al. (2012), J. Phys. Chem. Ref. Data 41, 033102,
                           doi:10.1063/1.4738955
             densitas & cp - formulasi IAPWS-95 (via NIST Chemistry WebBook)
  Silikon  : Glassbrenner & Slack (1964), Phys. Rev. 134, A1058, doi:10.1103/PhysRev.134.A1058
  Al 6061-T6 dan tembaga : data material ASM International (lembar data, tanpa DOI)

SILAKAN sesuaikan nilai dengan library material yang Anda pakai di Autodesk CFD
agar analisis konsisten dengan simulasi.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Fluid:
    name: str
    rho: float   # kg/m3
    mu: float    # Pa.s
    k: float     # W/m.K
    cp: float    # J/kg.K

    @property
    def Pr(self) -> float:
        return self.mu * self.cp / self.k


@dataclass(frozen=True)
class Solid:
    name: str
    k: float     # W/m.K
    rho: float   # kg/m3


WATER_25C = Fluid("Air (25 degC)", rho=997.0, mu=0.890e-3, k=0.61, cp=4180.0)
# Material "Water" bawaan Autodesk CFD (dipakai pada simulasi CFD ThermoChip)
WATER_AUTODESK = Fluid("Water Autodesk CFD", rho=998.2, mu=1.003e-3, k=0.6, cp=4182.0)
FLUIDS = {"autodesk": WATER_AUTODESK, "konstan": WATER_25C}

AL6061 = Solid("Al 6061-T6", k=167.0, rho=2700.0)
COPPER = Solid("Tembaga (C11000)", k=390.0, rho=8960.0)
SILICON = Solid("Silikon", k=148.0, rho=2330.0)

SOLIDS = {"al6061": AL6061, "copper": COPPER}
