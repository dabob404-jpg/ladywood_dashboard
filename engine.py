"""
engine.py
=========
Analytical Calculation Engine + Rehabilitation Recommendation Engine
for the Ladywood Environmental Monitoring & Rehabilitation Dashboard.

Implements the three engineering models specified in FEBE1004A Progress
Report 2, Section 6:

  6.1  Geomechanical Slope Stability  -> infinite-slope Factor of Safety
  6.2  Hydrological Surface Runoff    -> Rational Method (Q = C x I x A)
  6.3  Dust / Air Quality             -> UK Air Quality Objective thresholds

Reference sources for constants and thresholds (full citations in README.md):
  - BGS 1:50 000 bedrock geology (Mercia Mudstone Group / Sherwood
    Sandstone Group, west Birmingham) -- geotechnical parameter ranges.
  - CIRIA C580 / standard UK geotechnical reference ranges for made
    ground and weathered Triassic mudstone/sandstone.
  - BS EN 752 / Wallingford Procedure / FEH13 -- UK design storm
    practice (1-in-2-year routine design, 1-in-30-year flood check;
    ~50 mm/hr commonly used short-duration design intensity benchmark).
  - Air Quality Standards Regulations 2010 (PM10 24-hr objective
    50 ug/m3, annual 40 ug/m3) and Environment Act 2021 PM2.5 targets
    (12 ug/m3 interim 2028 target, 10 ug/m3 2040 target).
  - DEFRA UK-AIR monitoring stations "Birmingham Ladywood" and
    "Birmingham A4540 Roadside".
"""

from dataclasses import dataclass, field
import math

# ---------------------------------------------------------------------
# 1. ENGINEERING THRESHOLDS (as stated in Progress Report 2)
# ---------------------------------------------------------------------

FS_THRESHOLD_HIGH = 1.3        # FS < 1.3        -> High risk   (report Sec. 6.1)
FS_THRESHOLD_MODERATE = 1.5    # 1.3 <= FS < 1.5 -> Moderate risk

RUNOFF_EXCEEDANCE_HIGH = 1.00      # Q/Qcap >= 1.0 -> High risk (exceedance)
RUNOFF_EXCEEDANCE_MODERATE = 0.80  # Q/Qcap >= 0.8 -> Moderate risk

# UK Air Quality Objectives (Air Quality Standards Regulations 2010) and
# Environment Act 2021 PM2.5 targets.
PM10_ANNUAL_OBJECTIVE = 40.0       # ug/m3
PM10_24HR_OBJECTIVE = 50.0         # ug/m3 (not to be exceeded >35 times/yr)
PM25_UK_ANNUAL_OBJECTIVE = 20.0    # ug/m3 (2010 Regulations, "High" cutoff)
PM25_INTERIM_TARGET_2028 = 12.0    # ug/m3 (Environment Act 2021, "Moderate" cutoff)

DESIGN_RAINFALL_INTENSITY_MM_HR = 50.0  # UK short-duration design benchmark
                                         # (BS EN 752 legacy / Wallingford
                                         # Procedure practice; see README)


@dataclass
class RiskResult:
    value: float
    status: str          # "Low" | "Moderate" | "High"
    flagged: bool
    detail: str


# ---------------------------------------------------------------------
# 2. GEOMECHANICAL SLOPE STABILITY -- Infinite Slope Method
#
#    FS = [c' + (gamma - m * gamma_w) * z * cos^2(theta) * tan(phi')]
#         / [gamma * z * sin(theta) * cos(theta)]
#
#    m (saturation_ratio) scales the pore-water pressure term between a
#    dry slope (m=0) and a fully saturated slope (m=1); it lets each
#    zone reflect a partially saturated, more realistic condition
#    instead of assuming full saturation everywhere.
# ---------------------------------------------------------------------

def factor_of_safety(cohesion_kPa, unit_weight_kNm3, water_unit_weight_kNm3,
                      depth_m, slope_deg, friction_deg, saturation_ratio=1.0):
    theta = math.radians(slope_deg)
    phi = math.radians(friction_deg)
    gamma = unit_weight_kNm3
    gamma_w = water_unit_weight_kNm3
    z = depth_m
    m = saturation_ratio

    numerator = cohesion_kPa + (gamma - m * gamma_w) * z * (math.cos(theta) ** 2) * math.tan(phi)
    denominator = gamma * z * math.sin(theta) * math.cos(theta)
    if denominator <= 0:
        return float("inf")
    return numerator / denominator


def classify_slope_risk(fs):
    if fs < FS_THRESHOLD_HIGH:
        return RiskResult(
            value=fs, status="High", flagged=True,
            detail=f"FS = {fs:.2f} < {FS_THRESHOLD_HIGH} - flagged for further geotechnical investigation."
        )
    elif fs < FS_THRESHOLD_MODERATE:
        return RiskResult(
            value=fs, status="Moderate", flagged=False,
            detail=f"FS = {fs:.2f} - below comfortable margin, recommend monitoring."
        )
    else:
        return RiskResult(
            value=fs, status="Low", flagged=False,
            detail=f"FS = {fs:.2f} - stable under the simplified infinite-slope model."
        )


# ---------------------------------------------------------------------
# 3. HYDROLOGICAL SURFACE RUNOFF -- Rational Method
#
#    Q (L/s) = 2.78 * C * I(mm/hr) * A(ha)
#    (2.78 = unit-conversion constant for C dimensionless, I in mm/hr,
#     A in hectares, Q in litres/second; equivalent to the metric
#     Rational Method Q(m3/s) = C*I*A/360 used in UK drainage practice.)
# ---------------------------------------------------------------------

def peak_runoff_Ls(runoff_coefficient, intensity_mm_hr, area_ha):
    return 2.78 * runoff_coefficient * intensity_mm_hr * area_ha


def classify_runoff_risk(Q_Ls, Qcap_Ls):
    ratio = Q_Ls / Qcap_Ls if Qcap_Ls > 0 else float("inf")
    if ratio >= RUNOFF_EXCEEDANCE_HIGH:
        return RiskResult(
            value=ratio, status="High", flagged=True,
            detail=f"Q = {Q_Ls:.1f} L/s exceeds assumed drainage capacity of {Qcap_Ls:.0f} L/s ({ratio*100:.0f}%)."
        )
    elif ratio >= RUNOFF_EXCEEDANCE_MODERATE:
        return RiskResult(
            value=ratio, status="Moderate", flagged=False,
            detail=f"Q = {Q_Ls:.1f} L/s is at {ratio*100:.0f}% of drainage capacity - approaching exceedance."
        )
    else:
        return RiskResult(
            value=ratio, status="Low", flagged=False,
            detail=f"Q = {Q_Ls:.1f} L/s is within assumed drainage capacity ({ratio*100:.0f}%)."
        )


# ---------------------------------------------------------------------
# 4. DUST / AIR QUALITY -- UK Air Quality Objective thresholds
# ---------------------------------------------------------------------

def classify_pm10_risk(pm10_ugm3):
    if pm10_ugm3 >= PM10_24HR_OBJECTIVE:
        return RiskResult(pm10_ugm3, "High", True,
                           f"PM10 = {pm10_ugm3:.1f} ug/m3 >= {PM10_24HR_OBJECTIVE} ug/m3 24-hr objective.")
    elif pm10_ugm3 >= PM10_ANNUAL_OBJECTIVE * 0.7:
        return RiskResult(pm10_ugm3, "Moderate", False,
                           f"PM10 = {pm10_ugm3:.1f} ug/m3 - elevated relative to annual objective of {PM10_ANNUAL_OBJECTIVE} ug/m3.")
    else:
        return RiskResult(pm10_ugm3, "Low", False,
                           f"PM10 = {pm10_ugm3:.1f} ug/m3 - within UK objectives.")


def classify_pm25_risk(pm25_ugm3):
    if pm25_ugm3 >= PM25_UK_ANNUAL_OBJECTIVE:
        return RiskResult(pm25_ugm3, "High", True,
                           f"PM2.5 = {pm25_ugm3:.1f} ug/m3 >= {PM25_UK_ANNUAL_OBJECTIVE} ug/m3 UK annual objective.")
    elif pm25_ugm3 >= PM25_INTERIM_TARGET_2028:
        return RiskResult(pm25_ugm3, "Moderate", False,
                           f"PM2.5 = {pm25_ugm3:.1f} ug/m3 - above the 2028 interim target of {PM25_INTERIM_TARGET_2028} ug/m3.")
    else:
        return RiskResult(pm25_ugm3, "Low", False,
                           f"PM2.5 = {pm25_ugm3:.1f} ug/m3 - within current UK targets.")


# ---------------------------------------------------------------------
# 5. COMPOSITE ZONE RISK (Green / Yellow / Red, per report Sec. 5.2)
# ---------------------------------------------------------------------

def composite_zone_status(slope_result, runoff_result, dust10_result, dust25_result):
    statuses = [slope_result.status, runoff_result.status, dust10_result.status, dust25_result.status]
    if "High" in statuses:
        return "Red", "High Risk"
    elif "Moderate" in statuses:
        return "Yellow", "Moderate Risk"
    else:
        return "Green", "Low Risk"


def evaluate_zone(zone_row, rainfall_intensity_mm_hr=DESIGN_RAINFALL_INTENSITY_MM_HR):
    """Run all three engineering models for one zone (a dict-like row) and
    return a structured result bundle used by the dashboard."""
    fs = factor_of_safety(
        cohesion_kPa=zone_row["cohesion_kPa"],
        unit_weight_kNm3=zone_row["unit_weight_kNm3"],
        water_unit_weight_kNm3=zone_row["water_unit_weight_kNm3"],
        depth_m=zone_row["failure_depth_m"],
        slope_deg=zone_row["slope_angle_deg"],
        friction_deg=zone_row["friction_angle_deg"],
        saturation_ratio=zone_row["saturation_ratio"],
    )
    slope_result = classify_slope_risk(fs)

    Q = peak_runoff_Ls(
        runoff_coefficient=zone_row["runoff_coefficient"],
        intensity_mm_hr=rainfall_intensity_mm_hr,
        area_ha=zone_row["catchment_area_ha"],
    )
    runoff_result = classify_runoff_risk(Q, zone_row["drainage_capacity_Ls"])

    dust10_result = classify_pm10_risk(zone_row["pm10_ugm3"])
    dust25_result = classify_pm25_risk(zone_row["pm25_ugm3"])

    color, label = composite_zone_status(slope_result, runoff_result, dust10_result, dust25_result)

    return {
        "zone_id": zone_row["zone_id"],
        "zone_name": zone_row["zone_name"],
        "fs": fs,
        "slope_result": slope_result,
        "Q_Ls": Q,
        "runoff_result": runoff_result,
        "dust10_result": dust10_result,
        "dust25_result": dust25_result,
        "composite_color": color,
        "composite_label": label,
    }


# ---------------------------------------------------------------------
# 6. REHABILITATION RECOMMENDATION ENGINE (report Sec. 5.4 / 6.1-6.3)
#
#    Each intervention is scored 1 (poor) - 5 (excellent) on three
#    decision criteria so the Intervention Planner can rank strategies
#    by user-adjustable weights (Sec. "04 Rehabilitation Intervention
#    Planner" of the live dashboard). Scores are indicative, relative
#    engineering judgement values (not measured data) used to
#    demonstrate the trade-off logic; they should be refined with real
#    cost data during detailed design.
# ---------------------------------------------------------------------

INTERVENTIONS = [
    # domain, name, capital_cost (1=low..5=high), effectiveness (1..5), community_benefit (1..5)
    {"domain": "slope", "name": "Terraced slope stabilization", "cost": 4, "effectiveness": 5, "community": 3},
    {"domain": "slope", "name": "Vegetative slope stabilization", "cost": 2, "effectiveness": 3, "community": 4},
    {"domain": "slope", "name": "Improved surface-water drainage on slope", "cost": 3, "effectiveness": 4, "community": 3},
    {"domain": "slope", "name": "Retaining structures", "cost": 5, "effectiveness": 5, "community": 2},
    {"domain": "slope", "name": "Erosion control matting/geotextiles", "cost": 2, "effectiveness": 3, "community": 3},

    {"domain": "runoff", "name": "Vegetated bioswales", "cost": 2, "effectiveness": 3, "community": 5},
    {"domain": "runoff", "name": "Detention / settling basins", "cost": 4, "effectiveness": 5, "community": 3},
    {"domain": "runoff", "name": "Improved drainage channels", "cost": 3, "effectiveness": 4, "community": 3},
    {"domain": "runoff", "name": "Increased surface infiltration (permeable paving)", "cost": 3, "effectiveness": 3, "community": 4},
    {"domain": "runoff", "name": "Re-grading of catchment surface", "cost": 3, "effectiveness": 3, "community": 2},

    {"domain": "dust", "name": "Vegetative buffer zones", "cost": 2, "effectiveness": 3, "community": 5},
    {"domain": "dust", "name": "Surface stabilization of exposed ground", "cost": 2, "effectiveness": 4, "community": 3},
    {"domain": "dust", "name": "Dust suppression (water/binder application)", "cost": 1, "effectiveness": 3, "community": 3},
    {"domain": "dust", "name": "Reduction of loose surface material", "cost": 2, "effectiveness": 3, "community": 3},
    {"domain": "dust", "name": "Improved land-cover management", "cost": 3, "effectiveness": 4, "community": 4},
]


def flagged_domains(zone_eval):
    domains = []
    if zone_eval["slope_result"].status in ("High", "Moderate"):
        domains.append("slope")
    if zone_eval["runoff_result"].status in ("High", "Moderate"):
        domains.append("runoff")
    if zone_eval["dust10_result"].status in ("High", "Moderate") or zone_eval["dust25_result"].status in ("High", "Moderate"):
        domains.append("dust")
    return domains


def rank_interventions(zone_eval, w_cost=0.33, w_effectiveness=0.34, w_community=0.33):
    """Rank interventions relevant to a zone's flagged domains using a
    simple weighted-sum multi-criteria score. Lower cost is better, so
    cost is inverted (6 - cost) before weighting."""
    domains = flagged_domains(zone_eval)
    if not domains:
        return []

    total_w = w_cost + w_effectiveness + w_community
    if total_w == 0:
        w_cost = w_effectiveness = w_community = 1 / 3
    else:
        w_cost, w_effectiveness, w_community = (w_cost / total_w, w_effectiveness / total_w, w_community / total_w)

    ranked = []
    for item in INTERVENTIONS:
        if item["domain"] not in domains:
            continue
        cost_score = 6 - item["cost"]  # invert so low cost = high score
        score = (w_cost * cost_score) + (w_effectiveness * item["effectiveness"]) + (w_community * item["community"])
        ranked.append({**item, "score": round(score, 2)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked
