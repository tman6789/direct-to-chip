"""Parameter sweep utilities for ambient dry-bulb analysis."""

from __future__ import annotations

import numpy as np

from .calc import evaluate_design_point
from .models import DesignInputs, SweepRow


def sweep_ambient_drybulb(
    base_inputs: DesignInputs,
    amb_min_f: float = 40.0,
    amb_max_f: float = 115.0,
    step_f: float = 5.0,
) -> list[SweepRow]:
    """Sweep ambient dry-bulb and return a list of SweepRow results."""
    results: list[SweepRow] = []
    for amb in np.arange(amb_min_f, amb_max_f + step_f / 2, step_f):
        amb_val = float(amb)
        inp = base_inputs.model_copy(update={"ambient_drybulb_f": amb_val})
        out = evaluate_design_point(inp)
        results.append(
            SweepRow(
                ambient_db_f=amb_val,
                dry_cooler_feasible=out.dry_cooler_feasible,
                required_approach_f=out.required_approach_f,
                facility_supply_temp_f=out.facility_supply_temp_f,
                facility_return_temp_f=out.facility_return_temp_f,
                dry_cooler_leaving_temp_f=out.dry_cooler_leaving_temp_f,
                heat_reuse_potential_mw=out.heat_reuse_potential_mw_at_target,
            )
        )
    return results
