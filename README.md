# D2C Heat Rejection Model (d2c-hrm)

A screening-level tool that evaluates whether a data center's direct-to-chip (D2C) liquid cooling load can be rejected to atmosphere using **dry coolers only**, and quantifies **heat-reuse potential**.

> **MVP scope**: Design-point + parameter sweep. No 8760, no manufacturer curves, no external APIs.

---

## Quick Start

```bash
# Clone / unzip, then:
cd d2c-hrm
python -m venv .venv && source .venv\Scripts\activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Launch Streamlit UI
streamlit run app/streamlit_app.py
```

---

## Repo Structure

```
d2c-hrm/
├── app/
│   └── streamlit_app.py        # Streamlit web interface
├── src/d2c_hrm/
│   ├── __init__.py
│   ├── models.py               # Pydantic input/output data models
│   ├── calc.py                 # Core engineering calculations (pure functions)
│   ├── sweep.py                # Ambient dry-bulb parameter sweep
│   └── units.py                # Unit conversions & constants
├── tests/
│   └── test_core.py            # pytest unit tests
├── pyproject.toml
└── README.md
```

---

## Engineering Model

### Inputs

| Parameter | Default | Description |
|---|---|---|
| `it_load_mw` | 30 MW | Total IT electrical load |
| `fraction_to_liquid` | 0.80 | Fraction rejected via liquid (remainder = air-cooled, not modeled) |
| `liquid_loop_delta_t_f` | 18 °F | Cold-plate / CDU secondary ΔT |
| `target_chip_supply_temp_f` | 95 °F | Warm-water supply to cold plates |
| `ambient_drybulb_f` | 95 °F | Design ambient dry-bulb |
| `dry_cooler_approach_f` | 10 °F | T_fluid_leaving = T_amb + approach |
| `hx_effectiveness` | 0.90 | CDU liquid-to-liquid HX effectiveness (ε) |
| `facility_loop_delta_t_f` | 20 °F | Plant-side ΔT |
| `max_allowable_facility_supply_temp_f` | 105 °F | Material/controls limit |
| `heat_reuse_min_supply_temp_f` | 90 °F | Min temp for any heat recovery |
| `heat_reuse_target_temp_f` | 120 °F | Temp for 100% heat recovery fraction |
| `pump_power_fraction` | 0.02 | Pump kW as fraction of rejected thermal kW |
| `fan_power_kw_per_mw_rejected` | 20 | Dry cooler fan power (kW per MW rejected) |

### Core Formulas

**1. Load Decomposition**

```
liquid_load_kW = IT_load_MW × 1000 × fraction_to_liquid
```

**2. Chip Loop Temperatures**

```
chip_return = chip_supply + liquid_loop_ΔT
```

**3. Facility Loop via HX Effectiveness**

The CDU HX is modeled with a simplified effectiveness:

```
facility_supply = ambient_db + dry_cooler_approach   (what the dry cooler delivers)
facility_return = facility_supply + ε × (chip_return − facility_supply)
```

**4. Dry Cooler Feasibility**

```
required_approach = chip_supply − ambient_db
feasible  ⟺  dry_cooler_approach ≤ required_approach
```

If `ambient_db + approach > chip_supply`, the dry cooler cannot deliver fluid cold enough.

**5. Parasitic Power**

```
fan_kW   = fan_kW_per_MW_rejected × liquid_load_MW
pump_kW  = pump_power_fraction × liquid_load_kW
```

**6. Heat Reuse Potential**

Linear interpolation of recoverable fraction *f*:

```
if facility_supply ≥ reuse_target:   f = 1.0
elif facility_supply ≤ reuse_min:    f = 0.0
else: f = (facility_supply − reuse_min) / (reuse_target − reuse_min)

recoverable_MW = f × liquid_load_MW
```

**7. Flow Rates**

```
GPM = Q_Btuh / (500 × ΔT_°F)
where 500 ≈ 8.33 lb/gal × 60 min/hr × 1.0 Btu/(lb·°F)
```

---

## Example Scenarios

### Scenario 1 — Borderline (defaults)

30 MW IT, 80% liquid, 95 °F chip supply, 95 °F ambient, 10 °F approach.

| Parameter | Value |
|---|---|
| Liquid load | 24 MW / 24,000 kW |
| Chip return | 113 °F |
| Dry cooler leaving | 105 °F |
| Required approach | 0 °F (chip_supply − ambient) |
| Assumed approach | 10 °F |
| **Feasible?** | **NO** — dry cooler delivers 105 °F but chip needs ≤ 95 °F |
| Facility supply | 105 °F (capped at max) |
| Facility return | 112.2 °F |
| Fan power | 480 kW |
| Pump power | 480 kW |
| Heat reuse @ target | 12.0 MW (50% — supply 105 is midway between 90 and 120) |

### Scenario 2 — Cool Ambient

Same as Scenario 1 but **ambient = 55 °F**.

| Parameter | Value |
|---|---|
| Dry cooler leaving | 65 °F |
| Required approach | 40 °F |
| **Feasible?** | **YES** |
| Heat reuse @ target | 0 MW (65 °F < 90 °F min) |

### Scenario 3 — High Chip Supply (105 °F)

30 MW, 80% liquid, **105 °F** chip supply, 95 °F ambient, 10 °F approach.

| Parameter | Value |
|---|---|
| Chip return | 123 °F |
| Dry cooler leaving | 105 °F |
| Required approach | 10 °F |
| **Feasible?** | **YES** (10 ≤ 10) |
| Facility return | 121.2 °F |
| Heat reuse @ target | 12.0 MW (facility_supply = 105 → f = 0.5) |

---

## Validation Table — Scenario 1 Hand Calc vs Model

| Quantity | Hand Calc | Model Output | Match? |
|---|---|---|---|
| Liquid load (kW) | 30,000 × 0.8 = 24,000 | 24,000 | ✅ |
| Chip return (°F) | 95 + 18 = 113 | 113 | ✅ |
| DC leaving (°F) | 95 + 10 = 105 | 105 | ✅ |
| Fac. supply (°F) | min(105, 105) = 105 | 105 | ✅ |
| Fac. return (°F) | 105 + 0.9×(113−105) = 112.2 | 112.2 | ✅ |
| Required approach | 95 − 95 = 0 | 0 | ✅ |
| Feasible? | 10 > 0 → NO | NO | ✅ |
| Fan kW | 20 × 24 = 480 | 480 | ✅ |
| Pump kW | 0.02 × 24,000 = 480 | 480 | ✅ |
| Fac. GPM | 24,000×3412.14 / (500×20) = 8,189 | 8,189 | ✅ |
| Reuse fraction | (105−90)/(120−90) = 0.5 | 0.5 | ✅ |
| Reuse MW | 0.5 × 24 = 12 | 12 | ✅ |

---

## Assumptions & Caveats

1. **HX Model** — Simplified ε model; no ε-NTU or LMTD correction.
2. **Dry Cooler** — Constant approach; no part-load fan curves or VFD modeling.
3. **Parasitics** — Linear estimates only; no piping head-loss calculation.
4. **Heat Reuse** — Linear interpolation; real systems are non-linear.
5. **Fluid** — Water assumed (cp ≈ 1 Btu/lb·°F). Glycol de-rates ~10-20%.
6. **Hybrid/Wet Trim** — Not modeled; flagged when dry-only fails.
7. **Air-side** — Reported but not modeled for heat rejection.

---

## License

Internal engineering tool — not for redistribution.
