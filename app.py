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