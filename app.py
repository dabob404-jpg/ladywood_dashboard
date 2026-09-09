"""
Ladywood Environmental Monitoring & Rehabilitation Dashboard
FEBE1004A - Engineering Analysis and Design 1B - Progress Report 2 prototype

Run with:  streamlit run app.py
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import folium
from streamlit_folium import st_folium

import engine

st.set_page_config(page_title="Ladywood Environmental Dashboard", layout="wide")

# ----------------------------------------------------------------------
# DATA LOADING
# ----------------------------------------------------------------------

@st.cache_data
def load_zones():
    return pd.read_csv("data/zones.csv")


@st.cache_data
def evaluate_all(_df, rainfall_intensity):
    results = {}
    for _, row in _df.iterrows():
        results[row["zone_id"]] = engine.evaluate_zone(row, rainfall_intensity_mm_hr=rainfall_intensity)
    return results


zones_df = load_zones()

# ----------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------

st.markdown("###### Field Station · Ladywood, Birmingham")
st.title("Environmental Monitoring & Rehabilitation Console")
st.caption(
    "Applying mining-derived geomechanics, hydrology, and dust-monitoring methods to urban "
    "brownfield resilience.  52.4823° N, 1.9265° W"
)
st.info(
    "Prototype decision-support tool. Calculations use the simplified infinite-slope and "
    "Rational Method models specified in Progress Report 2 (Sec. 6). Zone parameters are "
    "grounded in real BGS geology, DEFRA/UK-AIR monitoring, and UK design-storm practice, "
    "but should not replace a site-specific geotechnical or hydrological investigation. "
    "See README.md for full data sources and assumptions.",
    icon="ℹ️",
)

# ----------------------------------------------------------------------
# SIDEBAR CONTROLS
# ----------------------------------------------------------------------

st.sidebar.header("Sidebar Control Panel")
rainfall_intensity = st.sidebar.slider(
    "Design rainfall intensity, I (mm/hr)",
    min_value=10.0, max_value=100.0, value=engine.DESIGN_RAINFALL_INTENSITY_MM_HR, step=1.0,
    help="Default 50 mm/hr reflects the UK short-duration design benchmark (BS EN 752 legacy / "
         "Wallingford Procedure practice). Increase to test a more severe storm event.",
)
st.sidebar.caption(
    "FEH13/Wallingford-derived M5-60min rainfall for the Birmingham region is of a similar "
    "order (~19-21 mm in 60 min); 50 mm/hr is the widely used UK short-duration channel design "
    "benchmark used here as the default 'engineering analysis' intensity."
)

results = evaluate_all(zones_df, rainfall_intensity)

# ----------------------------------------------------------------------
# SECTION 01 - GEOSPATIAL RISK HEAT MAP
# ----------------------------------------------------------------------

st.header("01 · Geospatial Risk Heat Map")
st.caption("Select a site zone on the map or panel")

color_map = {"Green": "#2ecc71", "Yellow": "#f1c40f", "Red": "#e74c3c"}

m = folium.Map(location=[52.4823, -1.9265], zoom_start=14, tiles="CartoDB positron")
for _, row in zones_df.iterrows():
    res = results[row["zone_id"]]
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=16,
        color=color_map[res["composite_color"]],
        fill=True,
        fill_color=color_map[res["composite_color"]],
        fill_opacity=0.75,
        popup=folium.Popup(
            f"<b>{row['zone_name']}</b><br>{res['composite_label']}<br>"
            f"FS={res['fs']:.2f} | Q={res['Q_Ls']:.0f} L/s | "
            f"PM10={row['pm10_ugm3']:.0f} | PM2.5={row['pm25_ugm3']:.0f}",
            max_width=250,
        ),
        tooltip=row["zone_name"],
    ).add_to(m)

map_col, legend_col = st.columns([3, 1])
with map_col:
    map_state = st_folium(m, height=430, width=None, returned_objects=["last_object_clicked_tooltip"])
with legend_col:
    st.markdown("**Legend**")
    st.markdown("🟢 Low Risk &nbsp;&nbsp; 🟡 Moderate Risk &nbsp;&nbsp; 🔴 High Risk")
    st.markdown("**Zones**")
    for _, row in zones_df.iterrows():
        res = results[row["zone_id"]]
        dot = {"Green": "🟢", "Yellow": "🟡", "Red": "🔴"}[res["composite_color"]]
        st.markdown(f"{dot} {row['zone_name']}")

# Determine selected zone: from map click, else selectbox fallback
clicked_name = None
if map_state and map_state.get("last_object_clicked_tooltip"):
    clicked_name = map_state["last_object_clicked_tooltip"]

default_index = 0
if clicked_name in list(zones_df["zone_name"]):
    default_index = list(zones_df["zone_name"]).index(clicked_name)

selected_zone_name = st.selectbox("Select a zone", zones_df["zone_name"], index=default_index)
selected_row = zones_df[zones_df["zone_name"] == selected_zone_name].iloc[0]
selected_result = results[selected_row["zone_id"]]

# ----------------------------------------------------------------------
# SECTION 02 - ZONE PROFILE ANALYSIS
# ----------------------------------------------------------------------

st.header("02 · Zone Profile Analysis")

profile_col1, profile_col2 = st.columns([1, 1])

with profile_col1:
    st.subheader(f"{selected_row['zone_name']}")
    st.caption(f"{selected_row['geology_unit']} · {selected_row['land_use']}")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Factor of Safety", f"{selected_result['fs']:.2f}", selected_result["slope_result"].status)
    k2.metric("Peak Runoff Q", f"{selected_result['Q_Ls']:.0f} L/s", selected_result["runoff_result"].status)
    k3.metric("PM10", f"{selected_row['pm10_ugm3']:.0f} ug/m3", selected_result["dust10_result"].status)
    k4.metric("PM2.5", f"{selected_row['pm25_ugm3']:.0f} ug/m3", selected_result["dust25_result"].status)

    st.markdown("**Indicator Breakdown**")
    st.write(f"- Slope stability: {selected_result['slope_result'].detail}")
    st.write(f"- Surface runoff: {selected_result['runoff_result'].detail}")
    st.write(f"- PM10: {selected_result['dust10_result'].detail}")
    st.write(f"- PM2.5: {selected_result['dust25_result'].detail}")

    with st.expander("Source parameters used for this zone"):
        st.write(selected_row["source_notes"])
        st.dataframe(selected_row.drop("source_notes").to_frame("value"))

with profile_col2:
    st.markdown("**Indicator Profile (Radar)**")

    # Normalise each indicator to a 0-100 "risk severity" scale for the radar
    def norm_fs(fs):
        return max(0, min(100, (2.0 - min(fs, 2.0)) / 2.0 * 100))

    def norm_ratio(r):
        return max(0, min(100, r * 100))

    def norm_pm(value, high_cutoff):
        return max(0, min(100, value / high_cutoff * 100))

    radar_values = [
        norm_fs(selected_result["fs"]),
        norm_ratio(selected_result["runoff_result"].value),
        norm_pm(selected_row["pm10_ugm3"], engine.PM10_24HR_OBJECTIVE),
        norm_pm(selected_row["pm25_ugm3"], engine.PM25_UK_ANNUAL_OBJECTIVE),
    ]
    radar_labels = ["Slope Risk", "Runoff Risk", "PM10 Risk", "PM2.5 Risk"]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_values + [radar_values[0]],
        theta=radar_labels + [radar_labels[0]],
        fill="toself",
        name=selected_row["zone_name"],
        line_color=color_map[selected_result["composite_color"]],
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, height=380, margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_radar, use_container_width=True)

# ----------------------------------------------------------------------
# SECTION 03 - CROSS-ZONE COMPARISON
# ----------------------------------------------------------------------

st.header("03 · Cross-Zone Comparison")
st.caption("Benchmark all five zones on one indicator")

indicator = st.radio(
    "Indicator",
    ["Factor of Safety", "Peak Runoff (L/s)", "PM10 (ug/m3)", "PM2.5 (ug/m3)"],
    horizontal=True,
)

compare_rows = []
for _, row in zones_df.iterrows():
    res = results[row["zone_id"]]
    compare_rows.append({
        "Zone": row["zone_name"],
        "Factor of Safety": res["fs"],
        "Peak Runoff (L/s)": res["Q_Ls"],
        "PM10 (ug/m3)": row["pm10_ugm3"],
        "PM2.5 (ug/m3)": row["pm25_ugm3"],
        "Composite": res["composite_color"],
    })
compare_df = pd.DataFrame(compare_rows)

threshold_lines = {
    "Factor of Safety": engine.FS_THRESHOLD_HIGH,
    "Peak Runoff (L/s)": None,
    "PM10 (ug/m3)": engine.PM10_24HR_OBJECTIVE,
    "PM2.5 (ug/m3)": engine.PM25_UK_ANNUAL_OBJECTIVE,
}

fig_bar = px.bar(
    compare_df, x="Zone", y=indicator, color="Composite",
    color_discrete_map={"Green": "#2ecc71", "Yellow": "#f1c40f", "Red": "#e74c3c"},
)
if threshold_lines[indicator] is not None:
    fig_bar.add_hline(y=threshold_lines[indicator], line_dash="dash", line_color="black",
                       annotation_text="risk threshold")
fig_bar.update_layout(height=420, showlegend=False)
st.plotly_chart(fig_bar, use_container_width=True)

# ----------------------------------------------------------------------
# SECTION 04 - REHABILITATION INTERVENTION PLANNER
# ----------------------------------------------------------------------

st.header("04 · Rehabilitation Intervention Planner")
st.caption(f"Adjust decision weights to rank strategies for: **{selected_row['zone_name']}**")

st.markdown("**Decision Weights**")
w1, w2, w3 = st.columns(3)
w_cost = w1.slider("Minimise capital cost", 0.0, 1.0, 0.33, 0.01)
w_effect = w2.slider("Maximise effectiveness", 0.0, 1.0, 0.34, 0.01)
w_comm = w3.slider("Maximise community benefit", 0.0, 1.0, 0.33, 0.01)

st.caption(
    "Trade-offs: Balance immediate capital costs against long-term community benefits and "
    "environmental stabilization effectiveness."
)

ranked = engine.rank_interventions(selected_result, w_cost, w_effect, w_comm)

st.markdown("**Ranked Interventions**")
if not ranked:
    st.success("No indicators are flagged Moderate or High for this zone — no rehabilitation "
               "intervention is currently triggered by the engine.")
else:
    ranked_df = pd.DataFrame(ranked)[["domain", "name", "cost", "effectiveness", "community", "score"]]
    ranked_df.columns = ["Domain", "Intervention", "Capital Cost (1-5)", "Effectiveness (1-5)",
                          "Community Benefit (1-5)", "Weighted Score"]
    ranked_df["Domain"] = ranked_df["Domain"].map(
        {"slope": "Slope stability", "runoff": "Surface runoff", "dust": "Dust / air quality"})
    st.dataframe(ranked_df, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Environmental Monitoring & Rehabilitation Planning Dashboard — School of Mining "
    "Engineering, Wits FEBE1004A, Group 24"
)
