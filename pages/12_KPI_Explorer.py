"""Role-aware self-service KPI explorer with minimum-group privacy protection."""

from __future__ import annotations

import re
from typing import Final

import duckdb
import pandas as pd
import streamlit as st

from release_config import DATABASE


MINIMUM_PRIVACY_GROUP_SIZE: Final = 5
METRIC_VIEWS: Final = {
    "M01": "m01_headcount",
    "M02": "m02_hires",
    "M03": "m03_exits",
    "M04": "m04_attrition_rate_monthly",
    "M05": "m05_attrition_rate_rolling_12m",
    "M07": "m07_gross_pay",
    "M09": "m09_employer_payroll_cost",
    "M13": "m13_attendance_rate",
    "M16": "m16_revenue",
    "M17": "m17_net_profit",
    "M18": "m18_operating_margin",
    "M22": "m22_task_completion_rate",
    "M23": "m23_on_time_delivery_rate",
    "M24": "m24_velocity",
    "M25": "m25_average_cycle_time",
    "M27": "m27_high_risk_share",
    "M29": "m29_net_hiring",
}
TEAM_METRICS = {"M22", "M23", "M24", "M25"}
ROLE_RULES: Final = {
    "ADMIN": {
        "metrics": set(METRIC_VIEWS),
        "dimensions": {"Company", "Department", "Team"},
        "description": "All governed aggregate metrics and drill levels.",
    },
    "HR": {
        "metrics": {"M01", "M02", "M03", "M04", "M05", "M07", "M09", "M13", "M27", "M29"},
        "dimensions": {"Company", "Department"},
        "description": "People and payroll aggregates; no team-level payroll detail.",
    },
    "MANAGER": {
        "metrics": TEAM_METRICS,
        "dimensions": {"Team"},
        "description": "Own-team delivery metrics only; small teams remain hidden.",
    },
    "EXECUTIVE": {
        "metrics": {"M01", "M03", "M04", "M05", "M13", "M16", "M17", "M18", "M29"},
        "dimensions": {"Company"},
        "description": "Company-level KPIs only.",
    },
}


def _minimum_group_size(value: object) -> int:
    match = re.match(r"^\s*(\d+)", str(value))
    return max(MINIMUM_PRIVACY_GROUP_SIZE, int(match.group(1))) if match else MINIMUM_PRIVACY_GROUP_SIZE


def _allowed_metrics(role: str, catalog: pd.DataFrame) -> pd.DataFrame:
    metric_ids = ROLE_RULES[role]["metrics"]
    return catalog.loc[catalog["metric_id"].isin(metric_ids)].sort_values("metric_name")


def _aggregate_company(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    latest = rows["period_start"].max()
    current = rows.loc[rows["period_start"] == latest].copy()
    numeric = current[["numerator", "denominator", "metric_value"]].sum(min_count=1)
    if numeric["denominator"] and current["unit"].iloc[0] in {"percent", "ratio"}:
        value = numeric["numerator"] / numeric["denominator"]
        if current["unit"].iloc[0] == "percent":
            value *= 100
    else:
        value = numeric["metric_value"]
    return pd.DataFrame(
        [{"group": "Company", "period_start": latest, "group_size": int(current["group_size"].sum()), "metric_value": value}]
    )


def _latest_groups(rows: pd.DataFrame, dimension: str, team_names: dict[str, str]) -> pd.DataFrame:
    if rows.empty:
        return rows
    rows = rows.copy()
    if dimension == "Department":
        rows["group"] = rows["department_id"].map(
            lambda value: f"{team_names.get(str(value), str(value))} · {value}"
        )
    else:
        rows["team_id"] = rows["breakdown_id"].astype(str).str.split("/", n=1).str[0]
        rows["group"] = rows["team_id"].map(
            lambda value: f"{team_names.get(str(value), str(value))} · {value}"
        )
    return (
        rows.sort_values(["period_start", "group"])
        .drop_duplicates("group", keep="last")
        [["group", "period_start", "group_size", "metric_value"]]
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_explorer_data(database_path: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        catalog = connection.execute("""
            SELECT metric_id, metric_name, unit, caveat, minimum_group_size
            FROM metrics.metric_catalog
            WHERE metric_id IN ('M01', 'M02', 'M03', 'M04', 'M05', 'M07', 'M09',
                                'M13', 'M16', 'M17', 'M18', 'M22', 'M23', 'M24',
                                'M25', 'M27', 'M29')
        """).fetchdf()
        departments = connection.execute("""
            SELECT department_id, department_name
            FROM metrics.dashboard_department_lookup
            ORDER BY department_name
        """).fetchdf()
        teams = connection.execute("""
            SELECT team_id, team_name, department_id
            FROM warehouse.dim_team
            ORDER BY team_name
        """).fetchdf()
    finally:
        connection.close()
    return catalog, departments, teams


def render_explorer() -> None:
    st.set_page_config(
        page_title="PulseIQ | KPI explorer",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
        :root { --ink: #172B4D; --muted: #667085; --teal: #087E8B; --paper: #F4F7FB; --line: #E4EAF1; }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
        .block-container { max-width: 1500px; padding: 2rem 2.4rem 3rem; }
        h1, h2, h3 { color: var(--ink); font-family: Inter, 'Segoe UI', sans-serif !important; }
        html, body, [class*="st-"], p, label { font-family: Inter, 'Segoe UI', sans-serif; }
        .hero-title { font: 750 36px Inter, 'Segoe UI', sans-serif; color: var(--ink); margin: 8px 0 5px; }
        .hero-copy { color: var(--muted); font-size: 15px; margin-bottom: 24px; }
        </style>
    """, unsafe_allow_html=True)

    try:
        catalog, departments, teams = load_explorer_data(str(DATABASE))
    except (duckdb.Error, OSError) as exc:
        st.error("The KPI explorer could not load its governed public data.")
        st.exception(exc)
        return

    usernames = {
        "admin.demo": "ADMIN",
        "hr.demo": "HR",
        "manager.demo": "MANAGER",
        "exec.demo": "EXECUTIVE",
    }
    username = st.sidebar.selectbox("Demo user", list(usernames), key="explorer_user")
    role = usernames[username]
    rules = ROLE_RULES[role]
    allowed = _allowed_metrics(role, catalog)
    if allowed.empty:
        st.error(f"No governed metrics are configured for the {role} role.")
        return

    st.sidebar.caption(f"Role: {role} · {rules['description']}")
    metric_id = st.sidebar.selectbox(
        "Metric",
        allowed["metric_id"].tolist(),
        format_func=lambda value: f"{value} · {allowed.set_index('metric_id').loc[value, 'metric_name']}",
    )
    dimension = st.sidebar.selectbox("Drill level", sorted(rules["dimensions"]))
    metric = allowed.loc[allowed["metric_id"] == metric_id].iloc[0]
    minimum_size = _minimum_group_size(metric["minimum_group_size"])

    st.markdown('<div class="hero-title">Self-service KPI explorer</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-copy">Choose a governed metric and drill from company to '
        'department or team without exposing small groups.</div>',
        unsafe_allow_html=True,
    )
    st.info(
        f"Demo role: {role}. Values are aggregate-only. Groups below {minimum_size} "
        "records are hidden; a manager team of 3 therefore receives no attrition "
        "or delivery value."
    )

    view_name = METRIC_VIEWS[metric_id]
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        rows = connection.execute(
            f"""
                SELECT period_start, department_id, breakdown_id, group_size,
                       numerator, denominator, metric_value, unit
                FROM metrics."{view_name}"
                WHERE data_status = 'AVAILABLE'
                  AND group_size >= ?
                ORDER BY period_start
            """,
            [minimum_size],
        ).fetchdf()
    finally:
        connection.close()

    team_names = teams.set_index("team_id")["team_name"].to_dict()
    department_names = departments.set_index("department_id")["department_name"].to_dict()
    if dimension == "Company":
        result = _aggregate_company(rows)
    elif dimension == "Department":
        result = _latest_groups(rows, dimension, department_names)
    else:
        if metric_id not in TEAM_METRICS:
            st.warning("Team drill-down is only available for governed delivery metrics.")
            return
        result = _latest_groups(rows, dimension, team_names)
        manager_team = teams.iloc[0]["team_id"] if role == "MANAGER" and not teams.empty else None
        if manager_team:
            result = result.loc[result["group"].str.endswith(f"· {manager_team}")]

    st.subheader(f"{metric_id} · {metric['metric_name']} · {dimension}")
    if result.empty:
        st.warning(
            f"No reportable {dimension.lower()} group meets the privacy minimum of "
            f"{minimum_size}. Nothing is displayed."
        )
        return
    result["metric_value"] = result["metric_value"].round(2)
    st.dataframe(
        result,
        width="stretch",
        hide_index=True,
        column_config={
            "group": "Group",
            "period_start": st.column_config.DateColumn("Latest period"),
            "group_size": st.column_config.NumberColumn("Protected group size"),
            "metric_value": st.column_config.NumberColumn(f"Value ({metric['unit']})"),
        },
    )
    st.caption(
        f"Privacy floor: {minimum_size} records. {metric['caveat'] or 'Use this governed aggregate in context.'}"
    )


render_explorer()
