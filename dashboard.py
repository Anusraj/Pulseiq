"""Shared Streamlit renderer for the PulseIQ workforce dashboard."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "pulseiq.duckdb"
INK = "#173D38"
TEAL = "#2E8173"
AMBER = "#C4813C"


@st.cache_data(ttl=600, show_spinner=False)
def load_dashboard_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        headcount = connection.execute("""
            SELECT period_start, department_id, metric_value AS headcount
            FROM metrics.m01_headcount
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        hires = connection.execute("""
            SELECT period_start, department_id, metric_value AS hires
            FROM metrics.m02_hires
            WHERE data_status = 'AVAILABLE'
        """).fetchdf()
        exits = connection.execute("""
            SELECT period_start, department_id, metric_value AS exits
            FROM metrics.m03_exits
            WHERE data_status = 'AVAILABLE'
        """).fetchdf()
        locations = connection.execute("""
            SELECT period_start, department_id, breakdown_id, metric_value AS headcount
            FROM metrics.dashboard_headcount_by_location_tier
            WHERE data_status = 'AVAILABLE'
        """).fetchdf()
        work_modes = connection.execute("""
            SELECT period_start, department_id, breakdown_id, metric_value AS headcount
            FROM metrics.dashboard_headcount_by_work_mode
            WHERE data_status = 'AVAILABLE'
        """).fetchdf()
        departments = connection.execute("""
            SELECT department_id, department_name
            FROM metrics.dashboard_department_lookup
        """).fetchdf()
    finally:
        connection.close()

    for frame in (headcount, hires, exits, locations, work_modes):
        frame["period_start"] = pd.to_datetime(frame["period_start"])
    return headcount, hires, exits, locations, work_modes, departments


def _finding_title(frame: pd.DataFrame, label: str) -> tuple[str, str]:
    if frame.empty:
        return f"No reportable {label.lower()} in this selection", ""
    total = float(frame["headcount"].sum())
    leader = frame.loc[frame["headcount"].idxmax()]
    share = 100 * float(leader["headcount"]) / total if total else 0
    return (
        f"{leader['breakdown_id']} leads {label.lower()} at {share:.0f}%",
        f"{leader['breakdown_id']} accounts for {int(leader['headcount']):,} of {int(total):,} reported people ({share:.1f}%).",
    )


def render_dashboard() -> None:
    st.set_page_config(
        page_title="PulseIQ | Workforce",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Baskerville:wght@700&display=swap');
        :root { --ink: #173D38; --teal: #2E8173; --amber: #C4813C; --paper: #F4F7F4; }
        .stApp { background-color: var(--paper); background-image: repeating-linear-gradient(135deg, rgba(23,61,56,.018) 0 1px, transparent 1px 8px); }
        [data-testid="stSidebar"] { background: #E8EFEB; border-right: 1px solid #D4DFD9; }
        h1, h2, h3 { color: var(--ink); font-family: 'Libre Baskerville', Georgia, serif !important; letter-spacing: 0 !important; }
        html, body, [class*="st-"], p, label { font-family: 'DM Sans', 'Segoe UI', sans-serif; letter-spacing: 0 !important; }
        .eyebrow { color: var(--teal); font: 700 12px 'DM Sans', sans-serif; text-transform: uppercase; letter-spacing: 0 !important; }
        .hero-title { font: 700 34px 'Libre Baskerville', Georgia, serif; color: var(--ink); margin: 4px 0 6px; }
        .hero-copy { color: #53665F; font-size: 15px; margin-bottom: 24px; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #DCE5DF; border-top: 3px solid var(--teal); padding: 15px 17px; border-radius: 4px; min-height: 118px; }
        [data-testid="stMetricLabel"] { color: #53665F; font-size: 13px; }
        [data-testid="stMetricValue"] { color: var(--ink); font-size: 27px; }
        [data-testid="stMetricDelta"] svg { display: none; }
        .finding { border-left: 3px solid var(--amber); padding: 9px 12px; margin: 2px 0 23px; color: #394C45; background: rgba(255,255,255,.66); font-size: 13px; }
        .section-label { color: #73827C; font-size: 11px; font-weight: 700; text-transform: uppercase; }
        [data-testid="stPlotlyChart"] { background: rgba(255,255,255,.85); border: 1px solid #E0E7E2; border-radius: 4px; padding: 8px; }
        @media (max-width: 720px) { .hero-title { font-size: 28px; } [data-testid="stMetric"] { min-height: 104px; padding: 12px; } }
        </style>
    """, unsafe_allow_html=True)

    try:
        headcount, hires, exits, locations, work_modes, departments = load_dashboard_data(str(DATABASE))
    except Exception as exc:
        st.error("The governed workforce views are not ready. Run `python metrics.py` after the ETL and warehouse builds.")
        st.exception(exc)
        return

    if headcount.empty:
        st.error("The headcount metric view returned no reportable rows.")
        return

    st.markdown('<div class="eyebrow">PulseIQ / People analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Workforce, at a glance</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-copy">A governed view of workforce size, composition and where the mix is shifting.</div>', unsafe_allow_html=True)

    department_names = departments.set_index("department_id")["department_name"].to_dict()
    department_options = sorted(headcount["department_id"].unique())
    department_labels = {key: f"{department_names.get(key, key)} · {key}" for key in department_options}
    st.sidebar.markdown('<div class="eyebrow">View controls</div>', unsafe_allow_html=True)
    selected_department = st.sidebar.selectbox(
        "Department", ["All reportable departments", *department_options],
        format_func=lambda value: "All reportable departments" if value == "All reportable departments" else department_labels[value],
    )
    dates = sorted(headcount["period_start"].drop_duplicates().tolist())
    default_start = dates[max(0, len(dates) - 12)]
    selected_dates = st.sidebar.select_slider(
        "Date range", options=dates, value=(default_start, dates[-1]),
        format_func=lambda value: value.strftime("%b %Y"),
    )
    start_date, end_date = pd.Timestamp(selected_dates[0]), pd.Timestamp(selected_dates[1])
    department_filter = selected_department != "All reportable departments"

    def scope(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.loc[frame["period_start"].between(start_date, end_date)].copy()
        if department_filter:
            result = result.loc[result["department_id"] == selected_department]
        return result

    trend = scope(headcount)
    hires_period = scope(hires)
    exits_period = scope(exits)
    if trend.empty:
        st.warning("No reportable rows match these filters.")
        return

    monthly = trend.groupby("period_start", as_index=False)["headcount"].sum().sort_values("period_start")
    first_value, latest_value = float(monthly.iloc[0]["headcount"]), float(monthly.iloc[-1]["headcount"])
    change = latest_value - first_value
    change_pct = (100 * change / first_value) if first_value else 0
    total_hires = float(hires_period["hires"].sum())
    total_exits = float(exits_period["exits"].sum())

    st.markdown('<div class="section-label">Current position and movement</div>', unsafe_allow_html=True)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Headcount", f"{int(latest_value):,}", help="Sum of departments that meet the official M01 minimum group size of five.")
    metric_columns[1].metric("Net change", f"{change:+,.0f}", f"{change_pct:+.1f}%")
    metric_columns[2].metric("Hires", f"{int(total_hires):,}")
    metric_columns[3].metric("Exits", f"{int(total_exits):,}")
    st.caption("Reportable department-level M01 headcount; hires and exits cover the selected range. Small groups are suppressed, so totals may exclude groups below five.")

    direction = "grew" if change > 0 else "declined" if change < 0 else "was unchanged"
    direction_text = f"{abs(change_pct):.1f}%" if change else "0%"
    st.subheader(f"Headcount {direction} {direction_text} across the selected period")
    line = px.line(monthly, x="period_start", y="headcount", markers=True)
    line.update_traces(line_color=TEAL, marker_color=AMBER, line_width=3, marker_size=7)
    line.update_layout(
        height=300, margin=dict(l=8, r=12, t=10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, Segoe UI, sans-serif", color=INK),
        xaxis_title=None, yaxis_title="People", hovermode="x unified",
    )
    st.plotly_chart(line, width="stretch", config={"displayModeBar": False})
    st.markdown(f'<div class="finding">Reportable headcount moved from {first_value:,.0f} to {latest_value:,.0f}, a net change of {change:+,.0f} people ({change_pct:+.1f}%).</div>', unsafe_allow_html=True)

    latest_period = monthly.iloc[-1]["period_start"]
    department_mix = trend.loc[trend["period_start"] == latest_period].groupby("department_id", as_index=False)["headcount"].sum()
    department_mix["department"] = department_mix["department_id"].map(department_labels)
    department_total = department_mix["headcount"].sum()
    leading_department = department_mix.loc[department_mix["headcount"].idxmax()]
    department_share = 100 * leading_department["headcount"] / department_total if department_total else 0
    st.subheader(f"{leading_department['department']} is the largest department at {department_share:.0f}%")
    bars = px.bar(department_mix.sort_values("headcount"), x="headcount", y="department", orientation="h", text="headcount")
    bars.update_traces(marker_color=TEAL, texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
    bars.update_layout(height=max(250, 32 * len(department_mix)), margin=dict(l=8, r=35, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans, Segoe UI, sans-serif", color=INK), xaxis_title="People", yaxis_title=None)
    st.plotly_chart(bars, width="stretch", config={"displayModeBar": False})
    st.markdown(f'<div class="finding">{leading_department["department"]} has {int(leading_department["headcount"]):,} people, {department_share:.1f}% of {int(department_total):,} reportable headcount.</div>', unsafe_allow_html=True)

    col_location, col_mode = st.columns(2)
    for column, frame, label in (
        (col_location, locations, "location tier"),
        (col_mode, work_modes, "work mode"),
    ):
        with column:
            filtered = scope(frame)
            current_mix = filtered.loc[filtered["period_start"] == latest_period].groupby("breakdown_id", as_index=False)["headcount"].sum()
            title, finding = _finding_title(current_mix, label)
            st.subheader(title)
            if current_mix.empty:
                st.info(f"No reportable {label} values for this selection.")
            else:
                chart = px.bar(current_mix.sort_values("headcount"), x="headcount", y="breakdown_id", orientation="h", text="headcount")
                chart.update_traces(marker_color=TEAL, texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                chart.update_layout(height=max(225, 52 * len(current_mix)), margin=dict(l=8, r=32, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans, Segoe UI, sans-serif", color=INK), xaxis_title="People", yaxis_title=None)
                st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
                st.markdown(f'<div class="finding">{finding} Groups below five are suppressed.</div>', unsafe_allow_html=True)

    st.caption(f"Latest month shown: {latest_period:%B %Y}. All values are sourced from the governed metrics views; tier and work-mode views use effective-dated employee attributes.")