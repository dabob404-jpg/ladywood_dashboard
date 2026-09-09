# Ladywood Environmental Monitoring & Rehabilitation Dashboard

Prototype for **FEBE1004A – Engineering Analysis and Design 1B, Progress Report 2**
(School of Mining Engineering, Wits, Group 24), implementing the design selected in
Section 5: a Python web app (Streamlit + Pandas + Folium + Plotly) with a real
calculation engine (Section 6) that flags risk and triggers the rehabilitation
measures listed in the report.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit apps run as a local (or deployed) server — they can't run inside a static
chat artifact, which is why this is delivered as a project you run yourself (or
deploy to Streamlit Community Cloud, which is free for a public GitHub repo).

## What's real vs. what's an assumption

This prototype follows the report's own guidance in Section 10.1: *"assumptions or
estimates may be used for demonstration purposes, but assumptions will be clearly
stated and will not be presented as measured site conditions."* Here's exactly
what's real and what's a documented engineering assumption.

### Real, sourced inputs

| Element | Source |
|---|---|
| Geology (Mercia Mudstone Group over Sherwood Sandstone Group, west Birmingham) | British Geological Survey 1:50 000 bedrock mapping; BGS Open Report OR/16/034 (Birmingham HS2 spur cross-sections) |
| PM10 / PM2.5 monitoring context | DEFRA UK-AIR stations **"Birmingham Ladywood"** (background) and **"Birmingham A4540 Roadside"** (kerbside), accessed via aqicn.org's UK-AIR feed |
| City-wide air quality status | All of Birmingham is a declared **Air Quality Management Area** under the Environment Act 1995; DEFRA modelling shows NO2 up to 50% above the legal limit (Birmingham City Council, via UKAuthority.com, 2023) |
| Design storm intensity | UK drainage practice — BS EN 752 (1-in-2-year routine design, 1-in-30-year flood check) and the widely used **50 mm/hr** short-duration design benchmark referenced in current UK drainage-industry guidance (ACO, 2024); order-of-magnitude consistent with FEH13/Wallingford M5-60min rainfall for the Birmingham region (~19–21 mm/hr) |
| UK Air Quality Objectives | Air Quality Standards Regulations 2010 (PM10: 40 µg/m³ annual / 50 µg/m³ 24-hr) and Environment Act 2021 PM2.5 targets (12 µg/m³ interim 2028, 10 µg/m³ 2040) |
| Zone locations | Five real, named sub-areas of Ladywood ward: Icknield Port Loop, Rotton Park Reservoir embankment, Ladywood Middleway/A4540 corridor, Five Ways/Ladywood housing estate, Summerfield Park |

### Engineering assumptions (clearly flagged, consistent with report Sec. 10.2)

- **Geotechnical parameters** (cohesion, friction angle, unit weight) per zone are
  typical published ranges for made ground and weathered Mercia Mudstone /
  Sherwood Sandstone (standard UK geotechnical reference ranges, e.g. CIRIA C580 /
  Hobbs 1998), not site-specific borehole/lab test results. A real project would
  replace these with site investigation data.
- **Drainage capacity** per zone is an assumed value reflecting Birmingham's largely
  Victorian-era combined sewer network, not measured hydraulic modelling of the
  actual sewer network.
- **PM10/PM2.5 values** assigned to each zone are representative of the range of
  real readings observed at the two nearest UK-AIR stations (background vs.
  roadside), not live per-zone sensor data — Ladywood does not have five separate
  monitoring stations.
- **Intervention cost/effectiveness/community-benefit scores** (1–5) used by the
  Rehabilitation Intervention Planner are indicative engineering-judgement values
  for demonstrating the multi-criteria trade-off logic, not quantity-surveyed costs.

## Engine logic (`engine.py`)

1. **Slope stability** — infinite-slope Factor of Safety (report Eq. in Sec. 6.1).
   Flags **High risk** if FS < 1.3 (the report's own threshold), **Moderate** if
   1.3 ≤ FS < 1.5.
2. **Surface runoff** — Rational Method, Q = C·I·A (report Eq. in Sec. 6.2), compared
   against each zone's assumed drainage capacity. Flags **High** if Q ≥ capacity,
   **Moderate** if Q ≥ 80% of capacity.
3. **Dust/air quality** — PM10 and PM2.5 compared against UK Air Quality Objectives
   (report Sec. 6.3). Flags **High** at/above the 24-hr PM10 objective or the PM2.5
   annual objective, **Moderate** at intermediate levels.
4. **Recommendation engine** — for every flagged domain (slope / runoff / dust), the
   engine filters a catalogue of the exact interventions named in the report
   (terracing, bioswales, vegetative buffers, etc.) and ranks them with a
   user-weighted multi-criteria score (cost vs. effectiveness vs. community
   benefit), matching the "Rehabilitation Intervention Planner" described in
   Section 5.4 of the report and Section 04 of the live dashboard.

## Files

```
app.py            Streamlit dashboard (4 sections matching the live site)
engine.py         Calculation + recommendation engine, thresholds, citations
data/zones.csv    Real zone locations + sourced/assumed parameters
requirements.txt  Python dependencies
```

## Known limitations

- This is a prototype decision-support tool, not a substitute for a site-specific
  geotechnical investigation or hydraulic drainage model (report Sec. 10.2).
- Air quality and rainfall values are representative reference figures, not a live
  DEFRA/Met Office API feed — extending the app to pull the UK-AIR API directly
  would be the natural next step for a production version.
