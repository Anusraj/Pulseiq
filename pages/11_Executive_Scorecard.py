"""Executive company-health scorecard."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pulseiq.duckdb"
GREEN = "#24845A"
AMBER = "#D98E32"
RED = "#C2413B"
INK = "#1F2937"

KPI_REASONS = {
    "Headcount": "Shows the scale of the workforce leaders are responsible for.",
    "Monthly attrition": "Signals whether retention is putting capacity and continuity at risk.",
    "Attendance rate": "Shows whether planned workforce capacity is showing up to work.",
    "Overtime share": "Highlights workload pressure and a controllable payroll cost driver.",
    "Revenue": "Anchors workforce decisions to the income the company is generating.",
    "Net profit": "Shows whether revenue is converting into cash-generating performance.",
    "Operating margin": "Shows how much of each revenue rupee remains after operating costs.",
    "Net hiring": "Shows whether the workforce is expanding or contracting this month.",
}

KPI_ORDER = [
    "Headcount",
    "Monthly attrition",
    "Attendance rate",
    "Overtime share",
    "Revenue",
    "Net profit",
    "Operating margin",
    "Net hiring",
]


@st.cache_data(ttl=600, show_spinner=False)
def load_scorecard(database_path: str) -> pd.DataFrame:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        scorecard = connection.execute(
            """
            SELECT period_start, kpi_id, kpi_name, metric_value, target_value,
                   unit, good_direction, traffic_light, source_view, detail_page
            FROM metrics.dashboard_executive_scorecard
            ORDER BY period_start, kpi_id
            """
        ).fetchdf()
    finally:
        connection.close()
    scorecard["period_start"] = pd.to_datetime(scorecard["period_start"])
    return scorecard


def status_label(value: str) -> str:
    return {
        "GREEN": "🟢 On target",
        "AMBER": "🟡 Watch",
        "RED": "🔴 Needs attention",
        "NO_TARGET": "⚪ Target not set",
    }.get(value, "⚪ Not available")


def format_value(value: object, unit: str) -> str:
    if pd.isna(value):
        return "—"
    if unit == "INR":
        return f"₹{float(value):,.0f}"
    if unit == "%":
        return f"{float(value):,.2f}%"
    return f"{float(value):,.0f}"


def format_target(value: object, unit: str) -> str:
    return "Not set" if pd.isna(value) else format_value(value, unit)


def render_kpi_card(row: pd.Series, previous: object) -> None:
    value = format_value(row["metric_value"], row["unit"])
    target = format_target(row["target_value"], row["unit"])
    if pd.isna(previous):
        trend = "—"
    else:
        difference = float(row["metric_value"]) - float(previous)
        trend = f"{difference:+,.2f} vs prior month"
    status = row["traffic_light"]
    color = {
        "GREEN": GREEN,
        "AMBER": AMBER,
        "RED": RED,
        "NO_TARGET": "#667085",
    }.get(status, "#667085")
    st.markdown(
        f"""
        <div class="scorecard-card" style="border-top: 5px solid {color};">
          <div class="scorecard-kpi">{row["kpi_name"]}</div>
          <div class="scorecard-value">{value}</div>
          <div class="scorecard-meta">Target: <strong>{target}</strong></div>
          <div class="scorecard-meta">Trend: <strong>{trend}</strong></div>
          <div class="scorecard-status">{status_label(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(row["detail_page"], label="Open detail page →")


def render_executive_scorecard_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Executive scorecard",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        @page { size: A4 landscape; margin: 10mm; }
        @media print {
          [data-testid="stSidebar"], [data-testid="stToolbar"],
          [data-testid="stHeader"], footer { display: none !important; }
          .block-container { max-width: none !important; padding: 0 !important; }
        }
        .scorecard-card {
          background: #F8FAFC;
          border-radius: 8px;
          min-height: 118px;
          padding: 12px 14px 8px;
          box-shadow: 0 1px 4px rgba(16, 24, 40, .12);
          color: #1F2937;
        }
        .scorecard-kpi { font-size: .86rem; font-weight: 700; }
        .scorecard-value { font-size: 1.55rem; font-weight: 800; margin: 6px 0; }
        .scorecard-meta { color: #667085; font-size: .76rem; line-height: 1.35; }
        .scorecard-status { font-size: .78rem; font-weight: 700; margin-top: 5px; }
        @media print {
          .scorecard-card { box-shadow: none; border: 1px solid #D0D5DD; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Executive company-health scorecard")
    st.caption(
        "Eight governed KPIs for a two-minute read. Values are company-level "
        "aggregates from metric views; targets come from kpi_targets where defined."
    )

    try:
        scorecard = load_scorecard(str(DATABASE))
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "The executive scorecard view is not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if scorecard.empty:
        st.error("No scorecard periods are available.")
        return

    month_counts = scorecard.groupby("period_start")["kpi_id"].nunique()
    months = sorted(month_counts[month_counts.eq(len(KPI_ORDER))].index.tolist())
    if not months:
        st.error("No month has all eight scorecard KPIs available.")
        return
    with st.sidebar:
        st.header("Scorecard filter")
        selected_month = st.selectbox(
            "Month",
            months,
            index=len(months) - 1,
            format_func=lambda value: value.strftime("%B %Y"),
        )

    selected = scorecard.loc[scorecard["period_start"].eq(selected_month)].copy()
    selected["sort_order"] = selected["kpi_name"].map(
        {name: index for index, name in enumerate(KPI_ORDER)}
    )
    selected = selected.sort_values("sort_order")
    if months.index(selected_month) > 0:
        prior = scorecard.loc[
            scorecard["period_start"].eq(months[months.index(selected_month) - 1])
        ]
        previous_values = prior.set_index("kpi_name")["metric_value"].to_dict()
    else:
        previous_values = {}

    status_counts = selected["traffic_light"].value_counts()
    summary = st.columns(4)
    summary[0].metric("KPIs on target", int(status_counts.get("GREEN", 0)))
    summary[1].metric("Needs attention", int(status_counts.get("RED", 0)))
    summary[2].metric("Targets not set", int(status_counts.get("NO_TARGET", 0)))
    summary[3].metric("Reporting month", selected_month.strftime("%B %Y"))

    rows = [selected.iloc[index:index + 4] for index in range(0, len(selected), 4)]
    for row_group in rows:
        columns = st.columns(4)
        for column, (_, row) in zip(columns, row_group.iterrows()):
            with column:
                previous = previous_values.get(row["kpi_name"], pd.NA)
                render_kpi_card(row, previous)

    st.divider()
    st.subheader("What each KPI tells the founder")
    reasons = pd.DataFrame(
        [
            {"KPI": name, "Why it matters": KPI_REASONS[name]}
            for name in KPI_ORDER
        ]
    )
    st.dataframe(reasons, hide_index=True, width="stretch")
    st.caption(
        "Traffic lights use kpi_targets for attendance, overtime and attrition. "
        "Other KPIs are shown as target not set because the source does not define "
        "a target; no target is invented. Trend is current value minus prior month."
    )


render_executive_scorecard_page()
