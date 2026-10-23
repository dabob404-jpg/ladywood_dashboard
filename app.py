"""
Ladywood Environmental Monitoring & Rehabilitation Dashboard
FEBE1004A - Engineering Analysis and Design 1B - Progress Report 2 prototype

Single-page, cross-filtering dashboard (Power BI style).
Run with:  streamlit run app.py
"""

import inspect

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import engine

st.set_page_config(
    page_title="Ladywood Environmental Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# STYLING
# ----------------------------------------------------------------------

COLOR_MAP = {"Green": "#2ecc71", "Yellow": "#f1c40f", "Red": "#e74c3c"}
RISK_NAME = {"Green": "Low", "Yellow": "Moderate", "Red": "High"}
NAVY = "#0f2a43"

st.markdown(
    f"""
    <style>
        .stApp {{ background: #f3f4f6; }}
        .block-container {{ padding-top: 1rem; padding-bottom: 1rem; max-width: 1650px; }}
        footer, #MainMenu {{ visibility: hidden; }}

        /* Panels (st.container(border=True)) */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: #ffffff; border: 1px solid #e5e7eb !important;
            border-radius: 10px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.07);
        }}

        /* Header band */
        .hdr {{
            background: linear-gradient(90deg, {NAVY} 0%, #1d4e75 100%);
            color: #fff; padding: 14px 22px; border-radius: 10px; margin-bottom: 12px;
        }}
        .hdr .eyebrow {{ font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.75; }}
        .hdr .title {{ font-size: 1.55rem; font-weight: 700; line-height: 1.25; color: #fff; }}
        .hdr .sub {{ font-size: 0.82rem; opacity: 0.85; color: #fff; }}

        /* KPI cards */
        .kpi {{
            background: #fff; border: 1px solid #e5e7eb; border-top: 4px solid var(--accent, #2563eb);
            border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.07);
        }}
        .kpi .lbl {{ font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: #6b7280; }}
        .kpi .val {{ font-size: 1.65rem; font-weight: 700; color: #111827; line-height: 1.2; }}
        .kpi .sub {{ font-size: 0.74rem; color: #6b7280; }}

        /* Panel titles */
        .ptitle {{ font-size: 0.95rem; font-weight: 700; color: {NAVY}; margin: 0 0 2px 0; }}
        .psub {{ font-size: 0.76rem; color: #6b7280; margin-bottom: 6px; }}
        .badge {{
            display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: 0.72rem; font-weight: 700; color: #fff;
        }}
        .tile {{
            background: #f9fafb; border: 1px solid #e5e7eb; border-left: 4px solid var(--accent, #9ca3af);
            border-radius: 8px; padding: 6px 10px; margin-bottom: 8px;
        }}
        .tile .lbl {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; }}
        .tile .val {{ font-size: 1.2rem; font-weight: 700; color: #111827; line-height: 1.2; }}
        .tile .sub {{ font-size: 0.72rem; color: #4b5563; }}

        [data-testid="stSidebar"] {{ border-right: 1px solid #e5e7eb; }}
    </style>
    """,
    unsafe_allow_html=True,
)

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
# SIDEBAR - SLICERS / FILTERS
# ----------------------------------------------------------------------

st.sidebar.header("Filters")
rainfall_intensity = st.sidebar.slider(
    "Design rainfall intensity, I (mm/hr)",
    min_value=10.0, max_value=100.0, value=engine.DESIGN_RAINFALL_INTENSITY_MM_HR, step=1.0,
    help="Default 50 mm/hr reflects the UK short-duration design benchmark (BS EN 752 legacy / "
         "Wallingford Procedure practice). FEH13/Wallingford-derived M5-60min rainfall for the "
         "Birmingham region is of a similar order (~19-21 mm in 60 min); 50 mm/hr is the widely "
         "used UK short-duration channel design benchmark used here as the default. "
         "Increase to test a more severe storm event.",
)

results = evaluate_all(zones_df, rainfall_intensity)

risk_filter = st.sidebar.multiselect(
    "Composite risk level",
    options=["Green", "Yellow", "Red"],
    default=["Green", "Yellow", "Red"],
    format_func=lambda c: RISK_NAME[c],
    help="Show only zones with the selected composite risk level. Applies to every visual.",
)

zones_df = zones_df.copy()
zones_df["_risk"] = zones_df["zone_id"].map(lambda z: results[z]["composite_color"])
view_df = zones_df[zones_df["_risk"].isin(risk_filter)].reset_index(drop=True)

if view_df.empty:
    st.warning("No zones match the current filters. Select at least one risk level in the sidebar.")
    st.stop()

zone_names = list(view_df["zone_name"])

# --- Selected-zone state (shared by map, bar chart and dropdown) -----------
if st.session_state.get("zone") not in zone_names:
    st.session_state["zone"] = zone_names[0]

# Cross-filter: a click on a bar in the comparison chart selects that zone
try:
    _bar_state = st.session_state.get("bar_chart")
    _pts = _bar_state["selection"]["points"] if _bar_state else []
    _bar_zone = _pts[0]["x"] if _pts else None
except Exception:
    _bar_zone = None
if _bar_zone != st.session_state.get("_last_bar_click"):
    st.session_state["_last_bar_click"] = _bar_zone
    if _bar_zone in zone_names:
        st.session_state["zone"] = _bar_zone


def _on_zone_change():
    st.session_state["zone"] = st.session_state["zone_sel"]


st.session_state["zone_sel"] = st.session_state["zone"]
st.sidebar.selectbox(
    "Selected zone", zone_names, key="zone_sel", on_change=_on_zone_change,
    help="You can also click a zone on the map or a bar in the comparison chart.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Decision weights")
w_cost = st.sidebar.slider("Minimise capital cost", 0.0, 1.0, 0.33, 0.01)
w_effect = st.sidebar.slider("Maximise effectiveness", 0.0, 1.0, 0.34, 0.01)
w_comm = st.sidebar.slider("Maximise community benefit", 0.0, 1.0, 0.33, 0.01)
st.sidebar.caption(
    "Trade-offs: balance immediate capital costs against long-term community benefits and "
    "environmental stabilisation effectiveness."
)

selected_zone_name = st.session_state["zone"]
selected_row = view_df[view_df["zone_name"] == selected_zone_name].iloc[0]
selected_result = results[selected_row["zone_id"]]
sel_color = COLOR_MAP[selected_result["composite_color"]]

# ----------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------

st.markdown(
    """
    <div class="hdr">
        <div class="eyebrow">Field Station · Ladywood, Birmingham · 52.4823° N, 1.9265° W</div>
        <div class="title">Environmental Monitoring &amp; Rehabilitation Console</div>
        <div class="sub">Applying mining-derived geomechanics, hydrology and dust-monitoring methods
        to urban brownfield resilience.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# KPI ROW (reacts to filters)
# ----------------------------------------------------------------------


def kpi(col, label, value, sub="", accent="#2563eb"):
    col.markdown(
        f'<div class="kpi" style="--accent:{accent}"><div class="lbl">{label}</div>'
        f'<div class="val">{value}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


fs_series = pd.Series({r["zone_name"]: results[r["zone_id"]]["fs"] for _, r in view_df.iterrows()})
q_series = pd.Series({r["zone_name"]: results[r["zone_id"]]["Q_Ls"] for _, r in view_df.iterrows()})
n_high = int((view_df["_risk"] == "Red").sum())
n_mod = int((view_df["_risk"] == "Yellow").sum())

k = st.columns(6)
kpi(k[0], "Zones in view", f"{len(view_df)} / {len(zones_df)}", "after filters")
kpi(k[1], "High-risk zones", str(n_high), f"{n_mod} moderate",
    COLOR_MAP["Red"] if n_high else COLOR_MAP["Green"])
kpi(k[2], "Lowest factor of safety", f"{fs_series.min():.2f}", fs_series.idxmin(), "#8b5cf6")
kpi(k[3], "Highest peak runoff", f"{q_series.max():.0f} L/s", q_series.idxmax(), "#0ea5e9")
kpi(k[4], "Mean PM10", f"{view_df['pm10_ugm3'].mean():.0f} µg/m³", "zones in view", "#f59e0b")
kpi(k[5], "Mean PM2.5", f"{view_df['pm25_ugm3'].mean():.0f} µg/m³", "zones in view", "#f97316")

st.write("")

# ----------------------------------------------------------------------
# ROW 1 - MAP  |  ZONE PROFILE
# ----------------------------------------------------------------------

row1_left, row1_right = st.columns([3, 2], gap="medium")

# ---- Geospatial risk map ---------------------------------------------
with row1_left:
    with st.container(border=True):
        st.markdown('<div class="ptitle">Geospatial Risk Heat Map</div>'
                    '<div class="psub">Click a zone to select it · '
                    '🟢 Low &nbsp; 🟡 Moderate &nbsp; 🔴 High</div>', unsafe_allow_html=True)

        m = folium.Map(location=[52.4823, -1.9265], zoom_start=14, tiles="OpenStreetMap")
        for _, row in view_df.iterrows():
            res = results[row["zone_id"]]
            is_sel = row["zone_name"] == selected_zone_name
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=18 if is_sel else 15,
                color="#111827" if is_sel else COLOR_MAP[res["composite_color"]],
                weight=3 if is_sel else 1,
                fill=True,
                fill_color=COLOR_MAP[res["composite_color"]],
                fill_opacity=0.85 if is_sel else 0.7,
                popup=folium.Popup(
                    f"<b>{row['zone_name']}</b><br>{res['composite_label']}<br>"
                    f"FS={res['fs']:.2f} | Q={res['Q_Ls']:.0f} L/s | "
                    f"PM10={row['pm10_ugm3']:.0f} | PM2.5={row['pm25_ugm3']:.0f}",
                    max_width=250,
                ),
                tooltip=row["zone_name"],
            ).add_to(m)

        map_state = st_folium(m, height=400, width=None, key="map",
                              returned_objects=["last_object_clicked_tooltip"])

# Cross-filter: map click selects zone
_clicked = map_state.get("last_object_clicked_tooltip") if map_state else None
if _clicked != st.session_state.get("_last_map_click"):
    st.session_state["_last_map_click"] = _clicked
    if _clicked in zone_names and _clicked != st.session_state["zone"]:
        st.session_state["zone"] = _clicked
        st.rerun()

# ---- Zone profile ----------------------------------------------------
with row1_right:
    with st.container(border=True):
        st.markdown(
            f'<div class="ptitle">{selected_row["zone_name"]} &nbsp;'
            f'<span class="badge" style="background:{sel_color}">'
            f'{RISK_NAME[selected_result["composite_color"]]} risk</span></div>'
            f'<div class="psub">{selected_row["geology_unit"]} · {selected_row["land_use"]}</div>',
            unsafe_allow_html=True,
        )

        def tile(col, label, value, status):
            col.markdown(
                f'<div class="tile" style="--accent:{sel_color}"><div class="lbl">{label}</div>'
                f'<div class="val">{value}</div><div class="sub">{status}</div></div>',
                unsafe_allow_html=True,
            )

        t1, t2 = st.columns(2)
        t3, t4 = st.columns(2)
        tile(t1, "Factor of Safety", f"{selected_result['fs']:.2f}", selected_result["slope_result"].status)
        tile(t2, "Peak Runoff", f"{selected_result['Q_Ls']:.0f} L/s", selected_result["runoff_result"].status)
        tile(t3, "PM10", f"{selected_row['pm10_ugm3']:.0f} µg/m³", selected_result["dust10_result"].status)
        tile(t4, "PM2.5", f"{selected_row['pm25_ugm3']:.0f} µg/m³", selected_result["dust25_result"].status)

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
            line_color=sel_color,
            fillcolor=sel_color,
            opacity=0.55,
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#e5e7eb"),
                       angularaxis=dict(gridcolor="#e5e7eb")),
            showlegend=False, height=225, margin=dict(t=15, b=15, l=40, r=40),
            template="plotly_white", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#374151"),
        )
        st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Indicator breakdown & source parameters"):
            st.write(f"- Slope stability: {selected_result['slope_result'].detail}")
            st.write(f"- Surface runoff: {selected_result['runoff_result'].detail}")
            st.write(f"- PM10: {selected_result['dust10_result'].detail}")
            st.write(f"- PM2.5: {selected_result['dust25_result'].detail}")
            st.caption(selected_row["source_notes"])
            st.dataframe(
                selected_row.drop(["source_notes", "_risk"]).astype(str).to_frame("value"),
                use_container_width=True,
            )

# ----------------------------------------------------------------------
# ROW 2 - CROSS-ZONE COMPARISON  |  INTERVENTION PLANNER
# ----------------------------------------------------------------------

row2_left, row2_right = st.columns([1, 1], gap="medium")

# ---- Cross-zone comparison -------------------------------------------
with row2_left:
    with st.container(border=True):
        st.markdown('<div class="ptitle">Cross-Zone Comparison</div>'
                    '<div class="psub">Benchmark zones on one indicator · click a bar to select '
                    'that zone</div>', unsafe_allow_html=True)

        indicator = st.radio(
            "Indicator",
            ["Factor of Safety", "Peak Runoff (L/s)", "PM10 (ug/m3)", "PM2.5 (ug/m3)"],
            horizontal=True, label_visibility="collapsed",
        )

        compare_rows = []
        for _, row in view_df.iterrows():
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

        is_sel_bar = compare_df["Zone"] == selected_zone_name
        fig_bar = go.Figure(go.Bar(
            x=compare_df["Zone"],
            y=compare_df[indicator],
            marker=dict(
                color=[COLOR_MAP[c] for c in compare_df["Composite"]],
                opacity=[1.0 if s else 0.55 for s in is_sel_bar],
                line=dict(color="#111827", width=0),
            ),
            selected=dict(marker=dict(opacity=1.0)),
            unselected=dict(marker=dict(opacity=0.55)),
            text=compare_df[indicator].map(lambda v: f"{v:.2f}" if indicator == "Factor of Safety" else f"{v:.0f}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>" + indicator + ": %{y:.2f}<extra></extra>",
        ))
        if threshold_lines[indicator] is not None:
            fig_bar.add_hline(y=threshold_lines[indicator], line_dash="dash", line_color="#374151",
                              annotation_text="risk threshold", annotation_position="top left")
        fig_bar.update_layout(
            height=300, showlegend=False, margin=dict(t=25, b=10, l=10, r=10),
            template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title=indicator, gridcolor="#e5e7eb"), xaxis=dict(title=None),
            font=dict(size=11, color="#374151"), clickmode="event+select",
        )

        _supports_select = "on_select" in inspect.signature(st.plotly_chart).parameters
        if _supports_select:
            st.plotly_chart(fig_bar, use_container_width=True, key="bar_chart",
                            on_select="rerun", selection_mode="points",
                            config={"displayModeBar": False})
        else:  # older Streamlit: chart still renders, just without click-to-select
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

# ---- Rehabilitation intervention planner -----------------------------
with row2_right:
    with st.container(border=True):
        st.markdown(f'<div class="ptitle">Rehabilitation Intervention Planner</div>'
                    f'<div class="psub">Ranked strategies for <b>{selected_row["zone_name"]}</b> · '
                    f'adjust the decision weights in the sidebar</div>', unsafe_allow_html=True)

        ranked = engine.rank_interventions(selected_result, w_cost, w_effect, w_comm)

        if not ranked:
            st.success("No indicators are flagged Moderate or High for this zone — no rehabilitation "
                       "intervention is currently triggered by the engine.")
        else:
            ranked_df = pd.DataFrame(ranked)[["domain", "name", "cost", "effectiveness", "community", "score"]]
            ranked_df.columns = ["Domain", "Intervention", "Capital Cost (1-5)", "Effectiveness (1-5)",
                                 "Community Benefit (1-5)", "Weighted Score"]
            ranked_df["Domain"] = ranked_df["Domain"].map(
                {"slope": "Slope stability", "runoff": "Surface runoff", "dust": "Dust / air quality"})
            st.dataframe(ranked_df, use_container_width=True, hide_index=True, height=300)

# ----------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------

with st.expander("About this prototype"):
    st.info(
        "Prototype decision-support tool. Calculations use the simplified infinite-slope and "
        "Rational Method models specified in Progress Report 2 (Sec. 6). Zone parameters are "
        "grounded in real BGS geology, DEFRA/UK-AIR monitoring, and UK design-storm practice, "
        "but should not replace a site-specific geotechnical or hydrological investigation. "
        "See README.md for full data sources and assumptions.",
        icon="ℹ️",
    )

st.caption(
    "Environmental Monitoring & Rehabilitation Planning Dashboard — School of Mining "
    "Engineering, Wits FEBE1004A, Group 24"
)
