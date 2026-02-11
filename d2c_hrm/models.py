"""Pydantic data models for the D2C Heat Rejection Model."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


# ── Design-Point Inputs ──────────────────────────────────────────────
class DesignInputs(BaseModel):
    """All user-adjustable inputs for a single design-point evaluation."""

    # IT load
    it_load_mw: float = Field(30.0, gt=0, description="Total IT electrical load (MW)")
    fraction_to_liquid: float = Field(
        0.80, ge=0, le=1, description="Fraction of IT load rejected via liquid cooling"
    )

    # Chip / CDU secondary loop
    liquid_loop_delta_t_f: float = Field(
        18.0, gt=0, description="Temperature rise across cold plates (°F)"
    )
    target_chip_supply_temp_f: float = Field(
        95.0, description="Warm-water supply to cold plates (°F)"
    )

    # Ambient conditions
    ambient_drybulb_f: float = Field(95.0, description="Design ambient dry-bulb (°F)")
    ambient_wetbulb_f: float | None = Field(
        None, description="Ambient wet-bulb (°F) – only used if hybrid trim enabled"
    )

    # Dry cooler
    dry_cooler_approach_f: float = Field(
        10.0, gt=0,
        description="Dry cooler approach: T_fluid_leaving = T_amb_db + approach (°F)",
    )

    # Liquid-to-liquid HX (CDU)
    hx_effectiveness: float = Field(
        0.90, gt=0, le=1, description="CDU HX effectiveness (ε)"
    )

    # Facility (plant) loop
    facility_loop_delta_t_f: float = Field(
        20.0, gt=0, description="Facility-side ΔT across dry cooler (°F)"
    )
    max_allowable_facility_supply_temp_f: float = Field(
        105.0, description="Max facility supply temp for materials/controls (°F)"
    )

    # Heat reuse
    heat_reuse_min_supply_temp_f: float = Field(
        90.0, description="Min facility supply temp for any heat reuse (°F)"
    )
    heat_reuse_target_temp_f: float = Field(
        120.0, description="Target facility supply temp for full heat reuse (°F)"
    )

    # Parasitics
    pump_power_fraction: float = Field(
        0.02, ge=0, le=0.10,
        description="Pump power as fraction of rejected thermal load",
    )
    fan_power_kw_per_mw_rejected: float = Field(
        20.0, ge=0,
        description="Dry cooler fan power (kW per MW of rejected heat)",
    )

    @model_validator(mode="after")
    def _validate_temps(self) -> "DesignInputs":
        if self.heat_reuse_min_supply_temp_f >= self.heat_reuse_target_temp_f:
            raise ValueError(
                "heat_reuse_min_supply_temp_f must be < heat_reuse_target_temp_f"
            )
        return self


# ── Design-Point Outputs ─────────────────────────────────────────────
class DesignOutputs(BaseModel):
    """All computed results for a single design point."""

    # Verdict
    dry_cooler_feasible: bool
    feasibility_note: str = ""

    # Temperatures (°F)
    chip_supply_temp_f: float
    chip_return_temp_f: float
    facility_supply_temp_f: float
    facility_return_temp_f: float
    dry_cooler_leaving_temp_f: float  # ambient + approach
    required_approach_f: float  # facility_return - ambient (what DC *needs*)
    assumed_approach_f: float  # user-specified dry cooler approach

    # Loads
    liquid_load_kw: float
    liquid_load_mw: float
    liquid_load_btuh: float
    air_load_kw: float  # portion NOT on liquid

    # Flow
    facility_loop_gpm: float
    chip_loop_gpm: float

    # Parasitics
    fan_power_kw: float
    pump_power_kw: float
    total_parasitic_kw: float
    parasitic_pct_of_it: float

    # Heat reuse
    heat_reuse_potential_mw_at_target: float
    heat_reuse_potential_mw_at_min: float

    class Config:
        json_schema_extra = {
            "example": {
                "dry_cooler_feasible": False,
                "chip_supply_temp_f": 95.0,
            }
        }


# ── Sweep result row ─────────────────────────────────────────────────
class SweepRow(BaseModel):
    ambient_db_f: float
    dry_cooler_feasible: bool
    required_approach_f: float
    facility_supply_temp_f: float
    facility_return_temp_f: float
    dry_cooler_leaving_temp_f: float
    heat_reuse_potential_mw: float
