"""Unit conversion utilities for D2C Heat Rejection Model.

All internal calculations use °F and kW unless otherwise noted.
"""

# ── Conversion constants ─────────────────────────────────────────────
MW_TO_KW: float = 1_000.0
KW_TO_BTUH: float = 3_412.14  # 1 kW = 3412.14 Btu/h
GAL_PER_MIN_PER_KW_10F_DT: float = 0.0455  # rough rule-of-thumb for water @ 10°F ΔT


def f_to_c(deg_f: float) -> float:
    """Convert temperature in °F to °C."""
    return (deg_f - 32.0) * 5.0 / 9.0


def c_to_f(deg_c: float) -> float:
    """Convert temperature in °C to °F."""
    return deg_c * 9.0 / 5.0 + 32.0


def delta_f_to_delta_c(delta_f: float) -> float:
    """Convert a temperature *difference* from °F to °C."""
    return delta_f * 5.0 / 9.0


def delta_c_to_delta_f(delta_c: float) -> float:
    """Convert a temperature *difference* from °C to °F."""
    return delta_c * 9.0 / 5.0


def mw_to_kw(mw: float) -> float:
    return mw * MW_TO_KW


def kw_to_mw(kw: float) -> float:
    return kw / MW_TO_KW


def kw_to_btuh(kw: float) -> float:
    return kw * KW_TO_BTUH


def btuh_to_kw(btuh: float) -> float:
    return btuh / KW_TO_BTUH


def gpm_for_load_and_dt(load_kw: float, delta_t_f: float) -> float:
    """Estimate GPM for a water loop given load (kW) and ΔT (°F).

    Q = m·cp·ΔT  →  GPM = Q_Btuh / (500 * ΔT_F)
    where 500 ≈ 8.33 lb/gal × 60 min/hr × 1 Btu/(lb·°F).
    """
    if delta_t_f <= 0:
        raise ValueError("delta_t_f must be > 0")
    btuh = kw_to_btuh(load_kw)
    return btuh / (500.0 * delta_t_f)
