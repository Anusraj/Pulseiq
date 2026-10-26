"""Attendance and leave trends backed by governed metric views."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pulseiq.duckdb"
TEAL = "#087E8B"
INK = "#172B4D"


@st.cache_data(ttl=600, show_spinner=False)
def load_attendance_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        attendance = connection.execute("""
            SELECT period_start, department_id, group_size, numerator, denominator,
                   metric_value AS attendance_rate
            FROM metrics.m13_attendance_rate
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        late_arrivals = connection.execute("""
            SELECT period_start, department_id, group_size, numerator AS late_arrivals,
                   denominator AS present_days, metric_value AS late_arrival_rate
            FROM metrics.m14_late_arrival_rate
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        overtime = connection.execute("""
            SELECT period_start, department_id, group_size, metric_value AS overtime_hours
            FROM metrics.dashboard_attendance_overtime
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id
        """).fetchdf()
        leave = connection.execute("""
            SELECT period_start, department_id, breakdown_id AS leave_type_code,
                   leave_type_name, group_size, metric_value AS leave_days
            FROM metrics.dashboard_leave_days_by_type
            WHERE data_status = 'AVAILABLE'
            ORDER BY period_start, department_id, breakdown_id
        """).fetchdf()
        calendar = connection.execute("""
            SELECT period_start, holiday_count, holiday_dates,
                   long_weekend_holiday_count, long_weekend_holiday_dates
            FROM metrics.dashboard_attendance_calendar
            ORDER BY period_start
        """).fetchdf()
        departments = connection.execute("""
            SELECT department_id, department_name
            FROM metrics.dashboard_department_lookup
        """).fetchdf()
    finally:
        connection.close()

    for frame in (attendance, late_arrivals, overtime, leave, calendar):
        frame["period_start"] = pd.to_datetime(frame["period_start"])
    return attendance, late_arrivals, overtime, leave, calendar, departments


def render_attendance_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Attendance and leave",
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
        .eyebrow { color: var(--teal); font: 700 11px Inter, 'Segoe UI', sans-serif; text-transform: uppercase; letter-spacing: .12em !important; }
        .hero-title { font: 750 36px Inter, 'Segoe UI', sans-serif; letter-spacing: -0.04em; color: var(--ink); margin: 8px 0 5px; }
        .hero-copy { color: var(--muted); font-size: 15px; margin-bottom: 28px; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--line); border-top: 3px solid var(--teal); padding: 16px 15px; border-radius: 12px; min-height: 122px; }
        [data-testid="stPlotlyChart"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 10px; }
        @media (max-width: 720px) { .block-container { padding: 1.25rem 1rem 2rem; } .hero-title { font-size: 29px; } }
        </style>
    """, unsafe_allow_html=True)

    try:
        attendance, late_arrivals, overtime, leave, calendar, departments = load_attendance_data(str(DATABASE))
    except (duckdb.Error, OSError) as exc:
        st.error(
            "Attendance views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if attendance.empty:
        st.error("The attendance metric view returned no reportable rows.")
        return

    department_names = departments.set_index("department_id")["department_name"].to_dict()
    department_options = sorted(attendance["department_id"].unique())
    all_departments = "All reportable departments"
    selected_department = st.sidebar.selectbox(
        "Department",
        [all_departments, *department_options],
        format_func=lambda value: all_departments
        if value == all_departments
        else f"{department_names.get(value, value)} · {value}",
    )
    dates = sorted(attendance["period_start"].drop_duplicates().tolist())
    default_start = dates[max(0, len(dates) - 12)]
    with st.sidebar.container(border=True):
        st.markdown('<div class="eyebrow">Reporting period</div>', unsafe_allow_html=True)
        date_columns = st.columns(2)
        start_month = date_columns[0].selectbox(
            "From", dates, index=dates.index(default_start),
            format_func=lambda value: value.strftime("%b %Y"),
            key="attendance_start_month",
        )
        end_month = date_columns[1].selectbox(
            "Through", dates, index=len(dates) - 1,
            format_func=lambda value: value.strftime("%b %Y"),
            key="attendance_end_month",
        )
    st.sidebar.caption(f"Available data: {dates[0]:%b %Y} – {dates[-1]:%b %Y}")
    start_date, end_date = pd.Timestamp(start_month), pd.Timestamp(end_month)
    if start_date > end_date:
        st.warning("Choose a reporting start month that is on or before the end month.")
        return

    department_filter = selected_department != all_departments

    def scope(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.loc[frame["period_start"].between(start_date, end_date)].copy()
        if department_filter and "department_id" in result.columns:
            result = result.loc[result["department_id"] == selected_department]
        return result

    attendance_period = scope(attendance)
    if attendance_period.empty:
        st.warning("No reportable rows match these filters.")
        return
    latest_period = attendance_period["period_start"].max()
    latest_attendance = attendance_period.loc[
        attendance_period["period_start"] == latest_period
    ]
    latest_numerator = float(latest_attendance["numerator"].sum())
    latest_denominator = float(latest_attendance["denominator"].sum())
    latest_rate = 100 * latest_numerator / latest_denominator if latest_denominator else 0
    latest_late = scope(late_arrivals)
    latest_late = latest_late.loc[latest_late["period_start"] == latest_period]
    latest_overtime = scope(overtime)
    latest_overtime = latest_overtime.loc[latest_overtime["period_start"] == latest_period]
    leave_period = scope(leave)
    selected_leave_days = float(leave_period["leave_days"].sum())

    st.markdown('<div class="eyebrow">PulseIQ / People analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Attendance & leave patterns</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-copy">Monthly presence, punctuality, overtime and approved leave, '
        'with the calendar alongside the trend.</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Reporting period: {start_date:%B %Y} – {end_date:%B %Y}")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Attendance rate", f"{latest_rate:.2f}%", f"{latest_period:%b %Y}")
    metric_columns[1].metric(
        "Late arrivals",
        f"{int(latest_late['late_arrivals'].sum()):,}",
        f"{latest_period:%b %Y}",
    )
    metric_columns[2].metric(
        "Overtime hours",
        f"{latest_overtime['overtime_hours'].sum():,.1f}",
        f"{latest_period:%b %Y}",
    )
    metric_columns[3].metric("Approved leave days", f"{selected_leave_days:,.0f}", "selected period")
    st.caption(
        "Attendance rate = (present days + 0.5 × unpaid half-days) ÷ scheduled working days. "
        "Department/type groups below five employees are suppressed."
    )

    selected_calendar = scope(calendar)
    calendar_by_month = selected_calendar.set_index("period_start")
    monthly = (
        attendance_period.groupby("period_start", as_index=False)[["numerator", "denominator"]]
        .sum()
        .sort_values("period_start")
    )
    monthly["attendance_pct"] = 100 * monthly["numerator"] / monthly["denominator"]
    monthly["holiday_count"] = monthly["period_start"].map(
        calendar_by_month["holiday_count"]
    ).fillna(0).astype(int)
    monthly["holiday_dates"] = monthly["period_start"].map(
        calendar_by_month["holiday_dates"]
    ).fillna("")
    monthly["long_weekend_holiday_dates"] = monthly["period_start"].map(
        calendar_by_month["long_weekend_holiday_dates"]
    ).fillna("")

    st.subheader("Attendance rate by month")
    st.caption("The all-department rate is weighted by scheduled working days, not an average of department percentages.")
    trend = px.line(
        monthly,
        x="period_start",
        y="attendance_pct",
        markers=True,
        custom_data=["holiday_count", "holiday_dates", "long_weekend_holiday_dates"],
    )
    trend.update_traces(
        line_color=TEAL,
        marker_color="#D98E32",
        line_width=3,
        hovertemplate=(
            "%{x|%b %Y}<br>Attendance: %{y:.2f}%"
            "<br>Holidays: %{customdata[0]} (%{customdata[1]})"
            "<br>Holiday dates adjacent to a weekend: %{customdata[2]}<extra></extra>"
        ),
    )
    trend.update_layout(
        height=330, margin=dict(l=8, r=12, t=10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, Segoe UI, sans-serif", color=INK),
        xaxis_title=None, yaxis_title="Attendance (%)", yaxis_ticksuffix="%",
        hovermode="x unified",
    )
    st.plotly_chart(trend, width="stretch", config={"displayModeBar": False})

    st.subheader("Department × month attendance heatmap")
    department_rates = scope(attendance)
    if department_rates.empty:
        st.info("No reportable department attendance values for this selection.")
    else:
        department_rates["attendance_pct"] = 100 * department_rates["attendance_rate"]
        heatmap_data = department_rates.pivot(
            index="department_id", columns="period_start", values="attendance_pct"
        ).sort_index()
        heatmap_data.index = [
            f"{department_names.get(department, department)} · {department}"
            for department in heatmap_data.index
        ]
        heatmap = px.imshow(
            heatmap_data,
            aspect="auto",
            text_auto=".1f",
            color_continuous_scale=["#F2B8A2", "#F6E6B4", "#8DC9B7"],
            zmin=80,
            zmax=100,
            labels={"x": "Month", "y": "Department", "color": "Attendance %"},
        )
        heatmap.update_layout(
            height=max(330, 38 * len(heatmap_data)),
            margin=dict(l=8, r=12, t=10, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans, Segoe UI, sans-serif", color=INK),
            coloraxis_colorbar_ticksuffix="%",
        )
        heatmap.update_xaxes(tickformat="%b\n%Y")
        st.plotly_chart(heatmap, width="stretch", config={"displayModeBar": False})

    left_chart, right_chart = st.columns(2)
    late_period = scope(late_arrivals).groupby("period_start", as_index=False)["late_arrivals"].sum()
    overtime_period = scope(overtime).groupby("period_start", as_index=False)["overtime_hours"].sum()
    with left_chart:
        st.subheader("Late arrivals")
        late_chart = px.bar(late_period, x="period_start", y="late_arrivals")
        late_chart.update_traces(marker_color="#D98E32")
        late_chart.update_layout(
            height=285, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Arrivals",
        )
        st.plotly_chart(late_chart, width="stretch", config={"displayModeBar": False})
    with right_chart:
        st.subheader("Overtime hours")
        overtime_chart = px.bar(overtime_period, x="period_start", y="overtime_hours")
        overtime_chart.update_traces(marker_color=TEAL)
        overtime_chart.update_layout(
            height=285, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Hours",
        )
        st.plotly_chart(overtime_chart, width="stretch", config={"displayModeBar": False})

    st.subheader("Approved leave days by type")
    if leave_period.empty:
        st.info("No reportable approved leave values for this selection.")
    else:
        leave_chart_data = (
            leave_period.groupby(["period_start", "leave_type_name"], as_index=False)["leave_days"]
            .sum()
        )
        leave_chart = px.bar(
            leave_chart_data,
            x="period_start",
            y="leave_days",
            color="leave_type_name",
            barmode="stack",
            labels={"period_start": "Month", "leave_days": "Leave days", "leave_type_name": "Leave type"},
        )
        leave_chart.update_layout(
            height=330, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Approved leave days",
        )
        st.plotly_chart(leave_chart, width="stretch", config={"displayModeBar": False})
        st.caption(
            "Leave days are assigned to the month the request starts; approved leave only. "
            "Each department × leave-type group is independently suppressed below five employees."
        )

    st.subheader("Holiday and long-weekend calendar")
    calendar_table = selected_calendar.copy()
    calendar_table["Month"] = calendar_table["period_start"].dt.strftime("%b %Y")
    calendar_table["Holiday dates"] = calendar_table["holiday_dates"].fillna("").replace("", "None")
    calendar_table["Holiday adjacent to weekend"] = (
        calendar_table["long_weekend_holiday_dates"].fillna("").replace("", "None")
    )
    st.dataframe(
        calendar_table[["Month", "holiday_count", "Holiday dates", "Holiday adjacent to weekend"]]
        .rename(columns={"holiday_count": "Holiday count"}),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Long-weekend markers identify holidays on Monday or Friday. Calendar context explains timing, "
        "but is not a causal adjustment to the scheduled-working-day attendance rate."
    )


render_attendance_page()
