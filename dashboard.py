"""Shared Streamlit renderer for the PulseIQ workforce dashboard."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from release_config import DATABASE
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
        net_hiring = connection.execute("""
            SELECT period_start, department_id, metric_value AS net_hires
            FROM metrics.m29_net_hiring
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

    for frame in (headcount, hires, exits, net_hiring, locations, work_modes):
        frame["period_start"] = pd.to_datetime(frame["period_start"])
    return headcount, hires, exits, net_hiring, locations, work_modes, departments


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
        :root { --ink: #172B4D; --muted: #667085; --teal: #087E8B; --amber: #D98E32; --paper: #F4F7FB; --line: #E4EAF1; }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: rgba(244,247,251,.88); }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
        [data-testid="stSidebar"] > div { padding-top: 1.5rem; }
        .block-container { max-width: 1500px; padding: 2rem 2.4rem 3rem; }
        h1, h2, h3 { color: var(--ink); font-family: Inter, 'Segoe UI', sans-serif !important; letter-spacing: -0.025em !important; }
        h2 { font-size: 1.35rem !important; font-weight: 650 !important; }
        html, body, [class*="st-"], p, label { font-family: Inter, 'Segoe UI', sans-serif; letter-spacing: 0 !important; }
        .eyebrow { color: var(--teal); font: 700 11px Inter, 'Segoe UI', sans-serif; text-transform: uppercase; letter-spacing: .12em !important; }
        .hero-title { font: 750 36px Inter, 'Segoe UI', sans-serif; letter-spacing: -0.04em; color: var(--ink); margin: 8px 0 5px; }
        .hero-copy { color: var(--muted); font-size: 15px; margin-bottom: 28px; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--line); border-top: 3px solid var(--teal); padding: 16px 15px; border-radius: 12px; min-height: 122px; box-shadow: 0 3px 12px rgba(23,43,77,.04); }
        [data-testid="stMetricLabel"] { color: var(--muted); font-size: 12px; font-weight: 600; }
        [data-testid="stMetricValue"] { color: var(--ink); font-size: 28px; font-weight: 700; }
        [data-testid="stMetricDelta"] svg { display: none; }
        .finding { border: 1px solid #F0E2CA; border-left: 4px solid var(--amber); padding: 12px 15px; margin: 3px 0 25px; color: #475467; background: #FFFCF7; font-size: 13px; border-radius: 0 10px 10px 0; }
        .section-label { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; }
        [data-testid="stPlotlyChart"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 10px; box-shadow: 0 3px 12px rgba(23,43,77,.035); }
        [data-testid="stSidebar"] [data-testid="stSelectbox"] { padding-bottom: .25rem; }
        [data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div { border-color: var(--line); border-radius: 9px; background: #FFFFFF; }
        @media (max-width: 720px) {
            .block-container { padding: 1.25rem 1rem 2rem; }
            .hero-title { font-size: 29px; }
            [data-testid="stMetric"] { min-height: 105px; padding: 12px; border-radius: 10px; }
            [data-testid="stMetricValue"] { font-size: 23px; }
        }
        </style>
    """, unsafe_allow_html=True)

    try:
        headcount, hires, exits, net_hiring, locations, work_modes, departments = load_dashboard_data(str(DATABASE))
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
    selected_department = st.sidebar.selectbox(
        "Department", ["All reportable departments", *department_options],
        format_func=lambda value: "All reportable departments" if value == "All reportable departments" else department_labels[value],
    )
    dates = sorted(headcount["period_start"].drop_duplicates().tolist())
    default_start = dates[max(0, len(dates) - 12)]
    with st.sidebar.container(border=True):
        st.markdown('<div class="eyebrow">Reporting period</div>', unsafe_allow_html=True)
        date_columns = st.columns(2)
        start_month = date_columns[0].selectbox(
            "From",
            dates,
            index=dates.index(default_start),
            format_func=lambda value: value.strftime("%b %Y"),
            key="reporting_start_month",
        )
        end_month = date_columns[1].selectbox(
            "Through",
            dates,
            index=len(dates) - 1,
            format_func=lambda value: value.strftime("%b %Y"),
            key="reporting_end_month",
        )
    st.sidebar.caption(f"Available data: {dates[0]:%b %Y} – {dates[-1]:%b %Y}")
    start_date, end_date = pd.Timestamp(start_month), pd.Timestamp(end_month)
    if start_date > end_date:
        st.warning("Choose a reporting start month that is on or before the end month.")
        return
    department_filter = selected_department != "All reportable departments"
    st.caption(f"Reporting period: {start_date:%B %Y} – {end_date:%B %Y}")
    try:
        metadata_connection = duckdb.connect(str(DATABASE), read_only=True)
        try:
            cutoff = metadata_connection.execute(
                "SELECT value FROM release_metadata WHERE key = 'data_cutoff'"
            ).fetchone()[0]
        finally:
            metadata_connection.close()
        st.caption(f"Data cut-off: {pd.Timestamp(cutoff):%d %B %Y} · Published aggregate snapshot")
    except duckdb.Error:
        st.caption("Data cut-off: available through the latest selected month")

    def scope(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.loc[frame["period_start"].between(start_date, end_date)].copy()
        if department_filter:
            result = result.loc[result["department_id"] == selected_department]
        return result

    trend = scope(headcount)
    hires_period = scope(hires)
    exits_period = scope(exits)
    net_hiring_period = scope(net_hiring)
    if trend.empty:
        st.warning("No reportable rows match these filters.")
        return

    monthly = trend.groupby("period_start", as_index=False)["headcount"].sum().sort_values("period_start")
    first_value, latest_value = float(monthly.iloc[0]["headcount"]), float(monthly.iloc[-1]["headcount"])
    change = latest_value - first_value
    change_pct = (100 * change / first_value) if first_value else 0
    total_hires = float(hires_period["hires"].sum())
    total_exits = float(exits_period["exits"].sum())
    total_net_hires = float(net_hiring_period["net_hires"].sum())

    st.markdown('<div class="section-label">Current position and movement</div>', unsafe_allow_html=True)
    metric_columns = st.columns(5)
    metric_columns[0].metric("Period-end headcount", f"{int(latest_value):,}")
    metric_columns[1].metric("Net change", f"{change:+,.0f}", f"{change_pct:+.1f}%")
    metric_columns[2].metric("Hires", f"{int(total_hires):,}")
    metric_columns[3].metric("Exits", f"{int(total_exits):,}")
    metric_columns[4].metric("Net hires", f"{int(total_net_hires):+,}")
    st.caption("Headcount is the latest month's ending count; movement metrics cover the selected range. Small groups are suppressed, so totals may exclude groups below five.")

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