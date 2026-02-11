"""Tests for d2c_hrm core calculations."""

import pytest

from d2c_hrm.calc import _heat_reuse_fraction, evaluate_design_point
from d2c_hrm.models import DesignInputs
from d2c_hrm.sweep import sweep_ambient_drybulb
from d2c_hrm.units import (
    c_to_f,
    delta_c_to_delta_f,
    delta_f_to_delta_c,
    f_to_c,
    gpm_for_load_and_dt,
    kw_to_btuh,
    mw_to_kw,
)


# ── Unit conversion tests ────────────────────────────────────────────

class TestUnits:
    def test_f_to_c_freezing(self) -> None:
        assert f_to_c(32.0) == pytest.approx(0.0)

    def test_f_to_c_boiling(self) -> None:
        assert f_to_c(212.0) == pytest.approx(100.0)

    def test_c_to_f_roundtrip(self) -> None:
        assert c_to_f(f_to_c(95.0)) == pytest.approx(95.0)

    def test_delta_conversions(self) -> None:
        assert delta_f_to_delta_c(18.0) == pytest.approx(10.0)
        assert delta_c_to_delta_f(10.0) == pytest.approx(18.0)

    def test_mw_to_kw(self) -> None:
        assert mw_to_kw(1.0) == 1000.0

    def test_kw_to_btuh(self) -> None:
        assert kw_to_btuh(1.0) == pytest.approx(3412.14)

    def test_gpm_for_load(self) -> None:
        # 1000 kW @ 20°F ΔT → Q = 1000*3412.14 Btuh, GPM = Q/(500*20)
        expected = 1000 * 3412.14 / (500 * 20)
        assert gpm_for_load_and_dt(1000, 20) == pytest.approx(expected, rel=1e-4)

    def test_gpm_zero_dt_raises(self) -> None:
        with pytest.raises(ValueError):
            gpm_for_load_and_dt(100, 0)


# ── Model validation tests ───────────────────────────────────────────

class TestModels:
    def test_default_inputs_valid(self) -> None:
        inp = DesignInputs()
        assert inp.it_load_mw == 30.0

    def test_fraction_bounds(self) -> None:
        with pytest.raises(Exception):
            DesignInputs(fraction_to_liquid=1.5)
        with pytest.raises(Exception):
            DesignInputs(fraction_to_liquid=-0.1)

    def test_reuse_temp_ordering(self) -> None:
        with pytest.raises(Exception):
            DesignInputs(heat_reuse_min_supply_temp_f=120, heat_reuse_target_temp_f=90)


# ── Heat reuse fraction tests ────────────────────────────────────────

class TestHeatReuse:
    def test_above_target(self) -> None:
        assert _heat_reuse_fraction(130, 90, 120) == 1.0

    def test_below_min(self) -> None:
        assert _heat_reuse_fraction(80, 90, 120) == 0.0

    def test_midpoint(self) -> None:
        assert _heat_reuse_fraction(105, 90, 120) == pytest.approx(0.5)

    def test_at_min(self) -> None:
        assert _heat_reuse_fraction(90, 90, 120) == 0.0

    def test_at_target(self) -> None:
        assert _heat_reuse_fraction(120, 90, 120) == 1.0


# ── Design-point scenario tests ──────────────────────────────────────

class TestDesignPoint:
    """Scenario 1: 30 MW, 80% liquid, 95°F supply, 95°F ambient, 10°F approach."""

    def test_scenario1_borderline(self) -> None:
        """95°F ambient + 10°F approach = 105°F leaving. chip_supply=95. NOT feasible."""
        inp = DesignInputs()  # all defaults = scenario 1
        out = evaluate_design_point(inp)

        # Chip temps
        assert out.chip_supply_temp_f == 95.0
        assert out.chip_return_temp_f == pytest.approx(113.0)  # 95+18

        # Dry cooler leaving = 95 + 10 = 105
        assert out.dry_cooler_leaving_temp_f == pytest.approx(105.0)

        # Feasibility: required_approach = 95 - 95 = 0, assumed = 10 → 10 > 0 → NOT feasible
        assert out.dry_cooler_feasible is False

        # Load
        assert out.liquid_load_mw == pytest.approx(24.0, rel=1e-3)
        assert out.liquid_load_kw == pytest.approx(24_000, rel=1e-3)

    def test_scenario2_cool_ambient(self) -> None:
        """55°F ambient → clearly feasible."""
        inp = DesignInputs(ambient_drybulb_f=55.0)
        out = evaluate_design_point(inp)

        # Dry cooler leaving = 55+10 = 65°F, well below 95 supply → feasible
        assert out.dry_cooler_feasible is True
        assert out.dry_cooler_leaving_temp_f == pytest.approx(65.0)

    def test_scenario3_high_supply(self) -> None:
        """105°F chip supply, 95°F ambient → required_approach = 10, assumed = 10 → feasible."""
        inp = DesignInputs(target_chip_supply_temp_f=105.0)
        out = evaluate_design_point(inp)

        assert out.dry_cooler_feasible is True
        assert out.chip_supply_temp_f == 105.0
        assert out.chip_return_temp_f == pytest.approx(123.0)

    def test_parasitic_range(self) -> None:
        out = evaluate_design_point(DesignInputs())
        # Parasitic should be a small % of IT
        assert 0 < out.parasitic_pct_of_it < 5.0

    def test_facility_return_gt_supply(self) -> None:
        """Facility return must be warmer than supply (heat gained in HX)."""
        out = evaluate_design_point(DesignInputs(ambient_drybulb_f=70.0))
        assert out.facility_return_temp_f > out.facility_supply_temp_f


# ── Sweep tests ──────────────────────────────────────────────────────

class TestSweep:
    def test_sweep_returns_rows(self) -> None:
        rows = sweep_ambient_drybulb(DesignInputs(), amb_min_f=50, amb_max_f=100, step_f=10)
        assert len(rows) == 6  # 50,60,70,80,90,100

    def test_sweep_feasibility_monotonic(self) -> None:
        """As ambient drops, feasibility should improve (or stay feasible)."""
        rows = sweep_ambient_drybulb(DesignInputs(), amb_min_f=40, amb_max_f=110, step_f=5)
        # Find transition: once infeasible, should stay infeasible at higher amb
        found_infeasible = False
        for r in rows:
            if not r.dry_cooler_feasible:
                found_infeasible = True
            if found_infeasible:
                assert not r.dry_cooler_feasible, (
                    f"Feasibility should not return after going infeasible (amb={r.ambient_db_f})"
                )
