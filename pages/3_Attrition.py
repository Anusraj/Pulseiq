"""Actual attrition analytics and privacy-safe attrition-risk predictions."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pulseiq.duckdb"
INK = "#172B4D"
TEAL = "#087E8B"
AMBER = "#D98E32"


@st.cache_data(ttl=600, show_spinner=False)
def load_attrition_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        exits = connection.execute("""
            SELECT period_start, department_id, group_size, numerator AS exits
            FROM metrics.m03_exits
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        monthly_rate = connection.execute("""
            SELECT period_start, department_id, group_size,
                   numerator AS exits, denominator AS average_headcount,
                   metric_value AS attrition_rate
            FROM metrics.m04_attrition_rate_monthly
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        exit_types = connection.execute("""
            SELECT department_id, exit_type, exits
            FROM metrics.dashboard_attrition_exit_types
            ORDER BY department_id, exit_type
        """).fetchdf()
        tenure = connection.execute("""
            SELECT department_id, tenure_band, exits
            FROM metrics.dashboard_attrition_tenure
            ORDER BY department_id, tenure_band
        """).fetchdf()
        risk = connection.execute("""
            SELECT period_start AS as_of_date, department_id, group_size,
                   numerator AS high_risk_people, metric_value AS high_risk_share
            FROM metrics.m27_high_risk_share
            WHERE data_status = 'AVAILABLE'
            ORDER BY department_id
        """).fetchdf()
        departments = connection.execute("""
            SELECT department_id, department_name
            FROM metrics.dashboard_department_lookup
            ORDER BY department_name
        """).fetchdf()
        thresholds = connection.execute("""
            SELECT metric_id, minimum_group_size_numeric
            FROM metrics.metric_catalog
            WHERE metric_id IN ('M03', 'M04', 'M27')
        """).fetchdf()
    finally:
        connection.close()

    for frame in (exits, monthly_rate, risk):
        date_column = "as_of_date" if frame is risk else "period_start"
        frame[date_column] = pd.to_datetime(frame[date_column])
    return exits, monthly_rate, exit_types, tenure, risk, departments, thresholds


def render_attrition_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Attrition",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
        :root { --ink: #172B4D; --muted: #667085; --teal: #087E8B; --paper: #F4F7FB; --line: #E4EAF1; }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: rgba(244,247,251,.88); }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
        .block-container { max-width: 1500px; padding: 2rem 2.4rem 3rem; }
        h1, h2, h3 { color: var(--ink); font-family: Inter, 'Segoe UI', sans-serif !important; letter-spacing: -0.025em !important; }
        html, body, [class*="st-"], p, label { font-family: Inter, 'Segoe UI', sans-serif; letter-spacing: 0 !important; }
        .hero-title { font: 750 36px Inter, 'Segoe UI', sans-serif; letter-spacing: -0.04em; color: var(--ink); margin: 8px 0 5px; }
        .hero-copy { color: var(--muted); font-size: 15px; margin-bottom: 24px; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--line); border-top: 3px solid var(--teal); padding: 16px 15px; border-radius: 12px; min-height: 115px; }
        [data-testid="stPlotlyChart"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 10px; }
        .finding { border: 1px solid #E4EAF1; border-left: 4px solid var(--teal); padding: 12px 15px; margin: 3px 0 12px; color: #475467; background: #FFFFFF; font-size: 13px; border-radius: 0 10px 10px 0; }
        @media (max-width: 720px) { .block-container { padding: 1.25rem 1rem 2rem; } .hero-title { font-size: 29px; } }
        </style>
    """, unsafe_allow_html=True)

    try:
        exits, monthly_rate, exit_types, tenure, risk, departments, thresholds = (
            load_attrition_data(str(DATABASE))
        )
    except (duckdb.Error, OSError) as exc:
        st.error(
            "Attrition views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py` after resolving "
            "any critical data-quality gate failures."
        )
        st.exception(exc)
        return

    if exits.empty:
        st.error("The governed exits view returned no reportable groups.")
        return

    minimums = thresholds.set_index("metric_id")["minimum_group_size_numeric"].to_dict()
    department_labels = departments.set_index("department_id")["department_name"].to_dict()
    all_departments = "All reportable departments"
    department_options = departments["department_id"].tolist()
    selected_department = st.sidebar.selectbox(
        "Department",
        [all_departments, *department_options],
        format_func=lambda value: all_departments
        if value == all_departments
        else f"{department_labels.get(value, value)} · {value}",
    )

    dates = sorted(exits["period_start"].drop_duplicates().tolist())
    default_start = dates[max(0, len(dates) - 12)]
    with st.sidebar.container(border=True):
        st.markdown("**Reporting period**")
        date_columns = st.columns(2)
        start_month = date_columns[0].selectbox(
            "From", dates, index=dates.index(default_start),
            format_func=lambda value: value.strftime("%b %Y"),
            key="attrition_start_month",
        )
        end_month = date_columns[1].selectbox(
            "Through", dates, index=len(dates) - 1,
            format_func=lambda value: value.strftime("%b %Y"),
            key="attrition_end_month",
        )
    st.sidebar.caption(f"Available data: {dates[0]:%b %Y} – {dates[-1]:%b %Y}")

    start_date, end_date = pd.Timestamp(start_month), pd.Timestamp(end_month)
    if start_date > end_date:
        st.warning("Choose a reporting start month that is on or before the end month.")
        return
    department_filter = selected_department != all_departments

    def period_scope(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.loc[frame["period_start"].between(start_date, end_date)].copy()
        if department_filter:
            result = result.loc[result["department_id"] == selected_department]
        return result

    exits_period = period_scope(exits)
    rate_period = period_scope(monthly_rate)
    tenure_period = tenure.copy()
    if department_filter:
        exit_types = exit_types.loc[exit_types["department_id"] == selected_department]
        tenure_period = tenure_period.loc[
            tenure_period["department_id"] == selected_department
        ]
    risk_period = risk.copy()
    if department_filter:
        risk_period = risk_period.loc[risk_period["department_id"] == selected_department]

    st.markdown('<div class="hero-title">Attrition: actual exits and risk</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-copy">Understand when and where exits occur, with a separate, '
        'privacy-safe view of predicted risk.</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Actual reporting period: {start_date:%B %Y} – {end_date:%B %Y}")

    st.header("Actual exits")
    st.caption(
        f"Department/month groups with fewer than {minimums['M03']} people are suppressed "
        "by the governed M03 view."
    )
    if exits_period.empty:
        st.info("No reportable exits match this department and date selection.")

    monthly_exits = (
        exits_period.groupby("period_start", as_index=False)["exits"]
        .sum()
        .sort_values("period_start")
    )
    department_exits = (
        exits_period.groupby("department_id", as_index=False)["exits"]
        .sum()
        .sort_values("exits", ascending=False)
    )
    latest_rate = rate_period.loc[rate_period["period_start"] == rate_period["period_start"].max()]
    weighted_rate = (
        100 * latest_rate["exits"].sum() / latest_rate["average_headcount"].sum()
        if not latest_rate.empty and latest_rate["average_headcount"].sum()
        else 0
    )
    kpi_columns = st.columns(3)
    kpi_columns[0].metric("Reportable exits", f"{int(exits_period['exits'].sum()):,}", "selected period")
    kpi_columns[1].metric(
        "Latest monthly attrition",
        f"{weighted_rate:.2f}%",
        f"{rate_period['period_start'].max():%b %Y}" if not rate_period.empty else "no reportable rate",
    )
    kpi_columns[2].metric(
        "Reportable department/month groups",
        f"{len(exits_period):,}",
        f"minimum {minimums['M03']} exits",
    )

    monthly_chart = px.bar(
        monthly_exits, x="period_start", y="exits",
        labels={"period_start": "Month", "exits": "Reportable exits"},
    )
    monthly_chart.update_traces(marker_color=TEAL)
    monthly_chart.update_layout(
        height=320, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title=None, yaxis_title="Reportable exits",
    )
    dept_chart_data = department_exits.copy()
    dept_chart_data["department"] = dept_chart_data["department_id"].map(department_labels)
    department_chart = px.bar(
        dept_chart_data.sort_values("exits"),
        x="exits", y="department", orientation="h",
        labels={"department": "Department", "exits": "Reportable exits"},
    )
    department_chart.update_traces(marker_color=AMBER)
    department_chart.update_layout(
        height=320, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Reportable exits", yaxis_title=None,
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Exits by month")
        st.plotly_chart(monthly_chart, width="stretch", config={"displayModeBar": False})
    with right:
        st.subheader("Exits by department")
        st.plotly_chart(department_chart, width="stretch", config={"displayModeBar": False})

    st.subheader("Voluntary and other exits")
    if exit_types.empty:
        st.info("No department has both exit types above the privacy threshold.")
    else:
        type_totals = exit_types.groupby(
            ["department_id", "exit_type"], as_index=False
        )["exits"].sum()
        type_totals["department"] = type_totals["department_id"].map(department_labels)
        type_chart = px.bar(
            type_totals, x="department", y="exits", color="exit_type",
            barmode="stack",
            color_discrete_map={"Voluntary": TEAL, "Other": AMBER},
            labels={"department": "Department", "exits": "Exits", "exit_type": "Exit type"},
        )
        type_chart.update_layout(
            height=300, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Exits",
        )
        st.plotly_chart(type_chart, width="stretch", config={"displayModeBar": False})
        st.caption(
            "All available history; department totals are shown only when both "
            f"categories meet the {minimums['M03']}-person minimum."
        )

    st.subheader("Tenure at exit")
    st.caption(
        "Tenure is calculated from hire date to last working day across all available history. "
        f"Department/tenure groups below {minimums['M04']} exits are suppressed."
    )
    if tenure_period.empty:
        st.info("No tenure groups meet the reporting threshold for this selection.")
    else:
        tenure_totals = tenure_period.groupby(
            ["tenure_band"], as_index=False
        )["exits"].sum()
        tenure_chart = px.bar(
            tenure_totals, x="tenure_band", y="exits",
            category_orders={"tenure_band": ["< 1 year", "1-< 3 years", "3-< 5 years", "5+ years"]},
            labels={"tenure_band": "Tenure at exit", "exits": "Reportable exits"},
        )
        tenure_chart.update_layout(
            height=310, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Reportable exits",
        )
        st.plotly_chart(tenure_chart, width="stretch", config={"displayModeBar": False})
        st.caption("Tenure distribution covers all available exit history, independent of the selected date range.")

    st.header("Three findings")
    if not monthly_exits.empty:
        peak_month = monthly_exits.loc[monthly_exits["exits"].idxmax()]
        st.markdown(
            f'<div class="finding">Peak reportable exit month: '
            f'<b>{peak_month["period_start"]:%B %Y}</b>, '
            f'{int(peak_month["exits"])} exits across reportable departments.</div>',
            unsafe_allow_html=True,
        )
    if not department_exits.empty:
        leading_department = department_exits.iloc[0]
        st.markdown(
            f'<div class="finding">Most reportable exits by department in this period: '
            f'<b>{department_labels.get(leading_department["department_id"], leading_department["department_id"])}</b>, '
            f'{int(leading_department["exits"])}.</div>',
            unsafe_allow_html=True,
        )
    latest_risk_date = risk["as_of_date"].max() if not risk.empty else None
    if not risk_period.empty:
        leading_risk = risk_period.loc[risk_period["high_risk_share"].idxmax()]
        st.markdown(
            f'<div class="finding">Highest reportable predicted high-risk share '
            f'on {latest_risk_date:%d %b %Y}: '
            f'<b>{department_labels.get(leading_risk["department_id"], leading_risk["department_id"])}</b>, '
            f'{leading_risk["high_risk_share"]:.2f}% '
            f'({int(leading_risk["high_risk_people"])} of {int(leading_risk["group_size"])} in the aggregate).</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="finding">Predicted-risk finding: no department group meets '
            f'the {minimums["M27"]}-person privacy threshold for this selection.</div>',
            unsafe_allow_html=True,
        )

    st.header("Predicted, not certain")
    if risk.empty:
        st.info("No reportable risk prediction groups are available.")
    else:
        st.caption(
            f"Latest available prediction snapshot: {latest_risk_date:%d %B %Y}. "
            "This snapshot is independent of the actual-exit date filter."
        )
        st.caption(
            f"Department risk groups below {minimums['M27']} people are suppressed. "
            "Only group-level high-risk share is displayed; no employee names or individual scores are shown."
        )
        st.caption(
            f"A department with fewer than {minimums['M27']} people, such as a four-person group, "
            "is omitted rather than shown as a percentage that could identify people."
        )
        if risk_period.empty:
            st.info("No risk group meets the privacy threshold for this department selection.")
        else:
            risk_chart_data = risk_period.copy()
            risk_chart_data["department"] = risk_chart_data["department_id"].map(department_labels)
            risk_chart = px.bar(
                risk_chart_data.sort_values("high_risk_share"),
                x="high_risk_share", y="department", orientation="h",
                labels={"department": "Department", "high_risk_share": "High-risk share (%)"},
                custom_data=["high_risk_people", "group_size"],
            )
            risk_chart.update_traces(
                marker_color=AMBER,
                hovertemplate=(
                    "%{y}<br>High-risk share: %{x:.2f}%"
                    "<br>High-risk people in aggregate: %{customdata[0]:.0f}"
                    "<br>Group size: %{customdata[1]:.0f}<extra></extra>"
                ),
            )
            risk_chart.update_layout(
                height=max(300, 38 * len(risk_chart_data)),
                margin=dict(l=8, r=8, t=8, b=8),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="High-risk share (%)", yaxis_title=None,
            )
            st.plotly_chart(risk_chart, width="stretch", config={"displayModeBar": False})
        st.info(
            "A risk prediction estimates a group-level pattern from the supplied model feed. "
            "It is not a confirmed future exit, a measure of an individual, or a decision rule. "
            "Use it to guide supportive conversations and review model freshness and fairness."
        )


render_attrition_page()
