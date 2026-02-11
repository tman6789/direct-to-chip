"""Streamlit UI for the D2C Heat Rejection Model."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from d2c_hrm.calc import evaluate_design_point
from d2c_hrm.models import DesignInputs
from d2c_hrm.sweep import sweep_ambient_drybulb

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="D2C Heat Rejection Model",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ Direct-to-Chip Liquid Cooling — Heat Rejection Model")
st.caption(
    "MVP design-point + parameter sweep for dry-cooler feasibility, "
    "parasitic loads, and heat-reuse potential."
)

# ── Sidebar inputs ────────────────────────────────────────────────────
with st.sidebar:
    st.header("Design Inputs")

    st.subheader("IT Load")
    it_load = st.number_input("IT Load (MW)", 0.1, 200.0, 30.0, 0.5)
    frac_liq = st.slider("Fraction to Liquid", 0.0, 1.0, 0.80, 0.05)

    st.subheader("Chip / CDU Loop")
    chip_supply = st.number_input("Chip Supply Temp (°F)", 60.0, 140.0, 95.0, 1.0)
    chip_dt = st.number_input("Liquid Loop ΔT (°F)", 5.0, 40.0, 18.0, 1.0)

    st.subheader("Ambient & Dry Cooler")
    amb_db = st.number_input("Ambient Dry-Bulb (°F)", 20.0, 130.0, 95.0, 1.0)
    dc_approach = st.number_input("Dry Cooler Approach (°F)", 2.0, 30.0, 10.0, 0.5)

    st.subheader("Heat Exchanger / Facility Loop")
    hx_eff = st.slider("HX Effectiveness (ε)", 0.5, 1.0, 0.90, 0.01)
    fac_dt = st.number_input("Facility Loop ΔT (°F)", 5.0, 40.0, 20.0, 1.0)
    max_fac_supply = st.number_input("Max Facility Supply Temp (°F)", 80.0, 150.0, 105.0, 1.0)

    st.subheader("Heat Reuse Thresholds")
    reuse_min = st.number_input("Min Supply for Reuse (°F)", 60.0, 130.0, 90.0, 1.0)
    reuse_target = st.number_input("Target Supply for Full Reuse (°F)", 80.0, 160.0, 120.0, 1.0)

    st.subheader("Parasitic Assumptions")
    pump_frac = st.slider("Pump Power (% of thermal)", 0.5, 5.0, 2.0, 0.1) / 100.0
    fan_kw = st.number_input("Fan Power (kW/MW rejected)", 5.0, 50.0, 20.0, 1.0)

# ── Build input model ─────────────────────────────────────────────────
try:
    inputs = DesignInputs(
        it_load_mw=it_load,
        fraction_to_liquid=frac_liq,
        liquid_loop_delta_t_f=chip_dt,
        target_chip_supply_temp_f=chip_supply,
        ambient_drybulb_f=amb_db,
        dry_cooler_approach_f=dc_approach,
        hx_effectiveness=hx_eff,
        facility_loop_delta_t_f=fac_dt,
        max_allowable_facility_supply_temp_f=max_fac_supply,
        heat_reuse_min_supply_temp_f=reuse_min,
        heat_reuse_target_temp_f=reuse_target,
        pump_power_fraction=pump_frac,
        fan_power_kw_per_mw_rejected=fan_kw,
    )
except Exception as e:
    st.error(f"Input validation error: {e}")
    st.stop()

# ── Run design point ──────────────────────────────────────────────────
out = evaluate_design_point(inputs)

# ── Results ───────────────────────────────────────────────────────────
col_v, col_t = st.columns([1, 2])

with col_v:
    st.subheader("Verdict")
    if out.dry_cooler_feasible:
        st.success("✅ DRY COOLER FEASIBLE", icon="✅")
    else:
        st.error("❌ DRY COOLER NOT FEASIBLE", icon="❌")
    st.info(out.feasibility_note)

    st.metric("Required Approach", f"{out.required_approach_f:.1f} °F")
    st.metric("Assumed Approach", f"{out.assumed_approach_f:.1f} °F")
    st.metric("Parasitic (% IT)", f"{out.parasitic_pct_of_it:.2f}%")

with col_t:
    st.subheader("Temperature Summary")
    temp_data = {
        "Parameter": [
            "Chip Supply", "Chip Return",
            "Facility Supply", "Facility Return",
            "Dry Cooler Leaving Fluid", "Ambient Dry-Bulb",
        ],
        "°F": [
            out.chip_supply_temp_f, out.chip_return_temp_f,
            out.facility_supply_temp_f, out.facility_return_temp_f,
            out.dry_cooler_leaving_temp_f, inputs.ambient_drybulb_f,
        ],
    }
    st.dataframe(pd.DataFrame(temp_data), hide_index=True, use_container_width=True)

    st.subheader("Load & Parasitic Summary")
    load_data = {
        "Parameter": [
            "Liquid Load (MW)", "Liquid Load (kW)", "Liquid Load (MBtuh)",
            "Air-Side Load (kW)",
            "Facility Loop GPM", "Chip Loop GPM",
            "Fan Power (kW)", "Pump Power (kW)", "Total Parasitic (kW)",
        ],
        "Value": [
            f"{out.liquid_load_mw:.2f}",
            f"{out.liquid_load_kw:,.0f}",
            f"{out.liquid_load_btuh / 1e6:,.2f}",
            f"{out.air_load_kw:,.0f}",
            f"{out.facility_loop_gpm:,.0f}",
            f"{out.chip_loop_gpm:,.0f}",
            f"{out.fan_power_kw:,.1f}",
            f"{out.pump_power_kw:,.1f}",
            f"{out.total_parasitic_kw:,.1f}",
        ],
    }
    st.dataframe(pd.DataFrame(load_data), hide_index=True, use_container_width=True)

# ── Heat reuse ────────────────────────────────────────────────────────
st.subheader("Heat Reuse Potential")
rc1, rc2 = st.columns(2)
rc1.metric("At Target Temp", f"{out.heat_reuse_potential_mw_at_target:.2f} MW")
rc2.metric("At Min Threshold", f"{out.heat_reuse_potential_mw_at_min:.2f} MW")

# ── Parameter sweep ───────────────────────────────────────────────────
st.divider()
st.subheader("Ambient Dry-Bulb Sweep")

with st.expander("Sweep Settings", expanded=False):
    sc1, sc2, sc3 = st.columns(3)
    amb_min = sc1.number_input("Sweep Min (°F)", 0.0, 100.0, 40.0, 5.0)
    amb_max = sc2.number_input("Sweep Max (°F)", 60.0, 130.0, 115.0, 5.0)
    amb_step = sc3.number_input("Step (°F)", 1.0, 20.0, 5.0, 1.0)

rows = sweep_ambient_drybulb(inputs, amb_min_f=amb_min, amb_max_f=amb_max, step_f=amb_step)
df = pd.DataFrame([r.model_dump() for r in rows])

# ── Feasibility plot ──────────────────────────────────────────────────
fig = go.Figure()

# Shading: feasible region
feasible_amb = [r.ambient_db_f for r in rows if r.dry_cooler_feasible]
if feasible_amb:
    fig.add_vrect(
        x0=min(feasible_amb), x1=max(feasible_amb),
        fillcolor="rgba(0,200,0,0.10)", line_width=0,
        annotation_text="Feasible", annotation_position="top left",
    )
infeasible_amb = [r.ambient_db_f for r in rows if not r.dry_cooler_feasible]
if infeasible_amb:
    fig.add_vrect(
        x0=min(infeasible_amb), x1=max(infeasible_amb),
        fillcolor="rgba(200,0,0,0.08)", line_width=0,
        annotation_text="Infeasible", annotation_position="top right",
    )

# Required approach line
fig.add_trace(go.Scatter(
    x=df["ambient_db_f"], y=df["required_approach_f"],
    mode="lines+markers", name="Required Approach (°F)",
    line=dict(color="#2563eb", width=2),
))

# Assumed approach (constant)
fig.add_hline(
    y=inputs.dry_cooler_approach_f,
    line_dash="dash", line_color="#dc2626",
    annotation_text=f"Assumed Approach = {inputs.dry_cooler_approach_f}°F",
)

fig.update_layout(
    title="Dry Cooler Feasibility vs Ambient Temperature",
    xaxis_title="Ambient Dry-Bulb (°F)",
    yaxis_title="Approach (°F)",
    height=450,
    template="plotly_white",
)
st.plotly_chart(fig, use_container_width=True)

# ── Heat reuse sweep plot ─────────────────────────────────────────────
fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df["ambient_db_f"], y=df["heat_reuse_potential_mw"],
    mode="lines+markers", name="Heat Reuse (MW)",
    line=dict(color="#059669", width=2),
    fill="tozeroy", fillcolor="rgba(5,150,105,0.12)",
))
fig2.update_layout(
    title="Heat Reuse Potential vs Ambient Temperature",
    xaxis_title="Ambient Dry-Bulb (°F)",
    yaxis_title="Recoverable Heat (MW)",
    height=350,
    template="plotly_white",
)
st.plotly_chart(fig2, use_container_width=True)

# ── Sweep data table ─────────────────────────────────────────────────
with st.expander("Sweep Data Table"):
    st.dataframe(df, hide_index=True, use_container_width=True)

# ── Design notes ──────────────────────────────────────────────────────
st.divider()
with st.expander("📋 Design Notes & Assumptions"):
    st.markdown("""
**Model Assumptions**

1. **HX Model**: Simplified effectiveness (ε) model assuming near-balanced capacity rates.
   `facility_return = facility_supply + ε · (chip_return − facility_supply)`.
   No detailed ε-NTU / LMTD correction is applied in this MVP.

2. **Dry Cooler**: Modeled as a constant-approach device:
   `T_fluid_leaving = T_ambient_db + approach`. No part-load fan curves or variable-speed correction.

3. **Parasitic Loads**: Fan and pump power are simple linear estimates
   (kW/MW rejected and fraction of load, respectively). No head-loss or system-curve modeling.

4. **Heat Reuse**: Linear interpolation of recoverable fraction between
   min and target supply temperatures. Real systems would have non-linear behavior.

5. **Fluid Properties**: Water assumed (cp ≈ 1 Btu/lb·°F, 8.33 lb/gal).
   Glycol mixtures would de-rate capacity ~10-20%.

6. **Wet/Hybrid Trim**: Not modeled in this MVP. Flagged when dry-only is infeasible.

7. **Air-side load** (1 − fraction_to_liquid) is reported but not modeled for rejection.

**Caveats**

- This is a **screening tool**, not a replacement for manufacturer selections.
- Real dry-cooler approach varies with air face velocity, coil rows, and fouling.
- Pump head and piping losses are not modeled; pump power is parametric only.
""")

# ── JSON export ───────────────────────────────────────────────────────
with st.expander("📦 Export Results (JSON)"):
    st.json(out.model_dump())
