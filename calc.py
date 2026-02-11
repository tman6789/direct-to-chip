"""Core engineering calculations for the D2C Heat Rejection Model.

All functions are pure (no side effects) and operate in °F / kW unless noted.

HEAT EXCHANGER MODEL (simplified ε approach)
────────────────────────────────────────────
We model the CDU as a counter-flow liquid-to-liquid heat exchanger with
effectiveness ε.  For equal-capacity-rate streams the relationship
simplifies to:

    T_cold_out = T_cold_in + ε · (T_hot_in − T_cold_in)

where:
    hot stream  = chip loop (hot side of CDU)
    cold stream = facility loop (cold side of CDU)

We know the *hot-side* inlet and outlet (chip_return, chip_supply) from
the cold-plate ΔT.  We solve for the facility-side temperatures that are
thermodynamically consistent:

    facility_return  = chip_return − (1 − ε) · (chip_return − facility_supply)
                     ≈ chip_return − (1−ε)·ΔT_chip  … when facility_supply ≈ chip_supply

The facility_supply is set by the dry cooler: ambient_db + approach.

DRY COOLER FEASIBILITY
──────────────────────
The dry cooler must cool the returning facility water from facility_return
down to facility_supply.  The minimum achievable leaving-fluid temperature
from the dry cooler is:

    T_min_leaving = ambient_db + approach

Feasibility: facility_supply (required by CDU cold-side inlet) can be met
if  T_min_leaving ≤ facility_supply.

    required_approach = facility_supply − ambient_db

If required_approach ≥ dry_cooler_approach → feasible.
"""

from __future__ import annotations

from .models import DesignInputs, DesignOutputs
from .units import gpm_for_load_and_dt, kw_to_btuh, kw_to_mw, mw_to_kw


def evaluate_design_point(inp: DesignInputs) -> DesignOutputs:
    """Run the full design-point calculation and return structured outputs."""

    # ── 1. Loads ──────────────────────────────────────────────────────
    it_load_kw = mw_to_kw(inp.it_load_mw)
    liquid_load_kw = it_load_kw * inp.fraction_to_liquid
    liquid_load_mw = kw_to_mw(liquid_load_kw)
    liquid_load_btuh = kw_to_btuh(liquid_load_kw)
    air_load_kw = it_load_kw - liquid_load_kw

    # ── 2. Chip loop temperatures ─────────────────────────────────────
    chip_supply = inp.target_chip_supply_temp_f
    chip_return = chip_supply + inp.liquid_loop_delta_t_f

    # ── 3. Facility loop via HX effectiveness ─────────────────────────
    #  Hot side: chip_return → chip_supply  (known)
    #  Cold side: facility_supply → facility_return  (to find)
    #
    #  With ε for the CDU HX (assuming balanced or near-balanced capacity rates):
    #    facility_return = facility_supply + ε · (chip_return − facility_supply)
    #
    #  facility_supply is what the dry cooler can deliver:
    #    facility_supply = ambient_db + dry_cooler_approach  (best case)
    #
    #  But we also need facility_supply ≤ chip_supply for sensible HX operation,
    #  AND ≤ max_allowable_facility_supply_temp_f.

    dry_cooler_leaving = inp.ambient_drybulb_f + inp.dry_cooler_approach_f

    # The facility supply temp is what the dry cooler can achieve
    facility_supply = dry_cooler_leaving

    # Cap at max allowable
    facility_supply = min(facility_supply, inp.max_allowable_facility_supply_temp_f)

    # HX cold-side outlet (facility return to dry cooler)
    facility_return = facility_supply + inp.hx_effectiveness * (
        chip_return - facility_supply
    )

    # ── 4. Dry cooler feasibility ─────────────────────────────────────
    #  The dry cooler must cool facility water from facility_return → facility_supply.
    #  The required approach is how close facility_supply needs to be to ambient.
    #  We check: can the dry cooler deliver facility_supply ≤ chip_supply?
    #  i.e., is dry_cooler_leaving ≤ chip_supply?
    required_approach = chip_supply - inp.ambient_drybulb_f
    assumed_approach = inp.dry_cooler_approach_f

    feasible = assumed_approach <= required_approach

    if feasible:
        note = (
            f"Dry cooler can deliver {dry_cooler_leaving:.1f}°F fluid, "
            f"which is at or below chip supply {chip_supply:.1f}°F."
        )
    else:
        note = (
            f"Dry cooler can only deliver {dry_cooler_leaving:.1f}°F fluid, "
            f"but chip supply requires ≤{chip_supply:.1f}°F. "
            f"Need {assumed_approach - required_approach:.1f}°F additional cooling "
            f"(hybrid / trim cooler needed)."
        )

    # ── 5. Flow rates ─────────────────────────────────────────────────
    facility_loop_gpm = gpm_for_load_and_dt(liquid_load_kw, inp.facility_loop_delta_t_f)
    chip_loop_gpm = gpm_for_load_and_dt(liquid_load_kw, inp.liquid_loop_delta_t_f)

    # ── 6. Parasitics ─────────────────────────────────────────────────
    fan_power_kw = inp.fan_power_kw_per_mw_rejected * liquid_load_mw
    pump_power_kw = inp.pump_power_fraction * liquid_load_kw
    total_parasitic = fan_power_kw + pump_power_kw
    parasitic_pct = (total_parasitic / it_load_kw) * 100.0 if it_load_kw > 0 else 0.0

    # ── 7. Heat reuse potential ───────────────────────────────────────
    reuse_at_target = _heat_reuse_fraction(
        facility_supply,
        inp.heat_reuse_min_supply_temp_f,
        inp.heat_reuse_target_temp_f,
    ) * liquid_load_mw

    reuse_at_min = _heat_reuse_fraction(
        facility_supply,
        inp.heat_reuse_min_supply_temp_f,
        inp.heat_reuse_min_supply_temp_f + 0.01,  # essentially step function at min
    ) * liquid_load_mw

    return DesignOutputs(
        dry_cooler_feasible=feasible,
        feasibility_note=note,
        chip_supply_temp_f=round(chip_supply, 2),
        chip_return_temp_f=round(chip_return, 2),
        facility_supply_temp_f=round(facility_supply, 2),
        facility_return_temp_f=round(facility_return, 2),
        dry_cooler_leaving_temp_f=round(dry_cooler_leaving, 2),
        required_approach_f=round(required_approach, 2),
        assumed_approach_f=round(assumed_approach, 2),
        liquid_load_kw=round(liquid_load_kw, 2),
        liquid_load_mw=round(liquid_load_mw, 4),
        liquid_load_btuh=round(liquid_load_btuh, 0),
        air_load_kw=round(air_load_kw, 2),
        facility_loop_gpm=round(facility_loop_gpm, 1),
        chip_loop_gpm=round(chip_loop_gpm, 1),
        fan_power_kw=round(fan_power_kw, 2),
        pump_power_kw=round(pump_power_kw, 2),
        total_parasitic_kw=round(total_parasitic, 2),
        parasitic_pct_of_it=round(parasitic_pct, 3),
        heat_reuse_potential_mw_at_target=round(reuse_at_target, 4),
        heat_reuse_potential_mw_at_min=round(reuse_at_min, 4),
    )


def _heat_reuse_fraction(
    facility_supply_f: float,
    reuse_min_f: float,
    reuse_target_f: float,
) -> float:
    """Return 0–1 fraction of liquid load recoverable for heat reuse.

    Linear interpolation between min and target supply temperatures.
    """
    if facility_supply_f >= reuse_target_f:
        return 1.0
    if facility_supply_f <= reuse_min_f:
        return 0.0
    return (facility_supply_f - reuse_min_f) / (reuse_target_f - reuse_min_f)
