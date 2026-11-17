"""Aggregate payroll costs by department and month."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


from pathlib import Path

from release_config import DATABASE
ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "cleaned" / "cleaning_report.csv"
TEAL = "#087E8B"
AMBER = "#D98E32"


@st.cache_data(ttl=600, show_spinner=False)
def load_payroll_data(database_path: str, report_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        monthly = connection.execute("""
            SELECT period_start, group_size AS employees_paid,
                   gross_pay, net_pay, employer_cost, cost_per_employee,
                   ledger_salary_related_expense, reconciliation_difference
            FROM metrics.dashboard_payroll_monthly_total
            ORDER BY period_start
        """).fetchdf()
        departments = connection.execute("""
            SELECT period_start, department_id, department_name, group_size,
                   gross_pay, net_pay, employer_cost, cost_per_employee
            FROM metrics.dashboard_payroll_department_month
            ORDER BY period_start, department_name
        """).fetchdf()
        thresholds = connection.execute("""
            SELECT metric_id, minimum_group_size_numeric
            FROM metrics.metric_catalog
            WHERE metric_id IN ('M07', 'M08', 'M09', 'M10')
        """).fetchdf()
    finally:
        connection.close()

    cleaning_report = pd.read_csv(report_path, dtype=str).fillna("")
    required_columns = {"action", "table", "record_id", "reason"}
    if not required_columns.issubset(cleaning_report.columns):
        raise ValueError("The cleaning report is missing required payroll audit columns.")
    payroll_exclusions = cleaning_report.loc[
        cleaning_report["table"].eq("fact_payroll")
        & cleaning_report["action"].isin(["deduplicated", "excluded"]),
        ["action", "record_id", "reason"],
    ].copy()
    payroll_exclusions["reason"] = payroll_exclusions.apply(
        lambda row: (
            "Exact duplicate employee/run record; original retained."
            if row["action"] == "deduplicated"
            else "Employee ID did not resolve to the employee dimension; excluded."
        ),
        axis=1,
    )
    payroll_exclusions["action"] = payroll_exclusions["action"].map(
        {"deduplicated": "Duplicate removed", "excluded": "Orphan excluded"}
    )
    monthly["period_start"] = pd.to_datetime(monthly["period_start"])
    departments["period_start"] = pd.to_datetime(departments["period_start"])
    return monthly, departments, thresholds, payroll_exclusions


def render_payroll_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Payroll cost",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Payroll cost")
    st.caption(
        "Monthly gross, net and employer payroll cost. Department figures come "
        "from governed metric views; only aggregate totals and averages are shown."
    )

    try:
        monthly, departments, thresholds, exclusions = load_payroll_data(
            str(DATABASE), str(REPORT)
        )
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "Payroll metric views or the cleaned-data audit report are not ready. "
            "Run `python etl.py`, `python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if monthly.empty or departments.empty:
        st.error("No payroll groups meet the minimum reporting threshold.")
        return

    minimum_size = int(thresholds["minimum_group_size_numeric"].max())
    months = monthly["period_start"].sort_values().tolist()
    month_labels = {month: month.strftime("%B %Y") for month in months}
    department_labels = (
        departments[["department_id", "department_name"]]
        .drop_duplicates()
        .sort_values("department_name")
        .set_index("department_id")["department_name"]
        .to_dict()
    )
    all_departments = "All departments"
    with st.sidebar:
        st.header("Report filters")
        selected_month = st.selectbox(
            "Month",
            months,
            index=len(months) - 1,
            format_func=lambda value: month_labels[value],
        )
        selected_department = st.selectbox(
            "Department",
            [all_departments, *department_labels],
            format_func=lambda value: (
                all_departments
                if value == all_departments
                else f"{department_labels[value]} · {value}"
            ),
        )

    selected_month_row = monthly.loc[
        monthly["period_start"].eq(selected_month)
    ].iloc[0]
    if selected_department == all_departments:
        metrics = selected_month_row
        trend = monthly.copy()
        month_departments = departments.loc[
            departments["period_start"].eq(selected_month)
        ].copy()
        group_caption = "Company-wide aggregate"
        display_departments = month_departments
    else:
        selected_rows = departments.loc[
            departments["period_start"].eq(selected_month)
            & departments["department_id"].eq(selected_department)
        ]
        if selected_rows.empty:
            st.info("This department has no reportable payroll group for the selected month.")
            return
        metrics = selected_rows.iloc[0]
        trend = departments.loc[
            departments["department_id"].eq(selected_department)
        ].copy()
        group_caption = f"{department_labels[selected_department]} · {selected_department}"
        display_departments = selected_rows

    st.subheader(f"{month_labels[selected_month]} · {group_caption}")
    cards = st.columns(4)
    cards[0].metric("Gross pay", f"₹{metrics['gross_pay']:,.2f}")
    cards[1].metric("Net pay", f"₹{metrics['net_pay']:,.2f}")
    cards[2].metric("Employer cost", f"₹{metrics['employer_cost']:,.2f}")
    cards[3].metric(
        "Cost per paid employee",
        f"₹{metrics['cost_per_employee']:,.2f}",
        help="Employer cost divided by distinct employees paid in this reportable group.",
    )
    if selected_department == all_departments:
        st.caption(f"Paid employees in the company-wide aggregate: {int(metrics['employees_paid']):,}.")

    difference = float(selected_month_row["reconciliation_difference"])
    if abs(difference) <= 0.01:
        st.success(
            "Company-wide employer payroll cost matches ledger salary-related expense "
            f"(accounts 5001–5005) for this month; difference ₹{difference:,.2f}."
        )
    else:
        st.warning(
            "Company-wide payroll and ledger do not reconcile for this month. "
            f"Payroll less ledger: ₹{difference:,.2f}."
        )

    st.subheader("Monthly trend")
    trend = trend.sort_values("period_start").copy()
    trend["period_label"] = trend["period_start"].dt.strftime("%b %Y")
    long_costs = trend.melt(
        id_vars=["period_start", "period_label"],
        value_vars=["gross_pay", "net_pay", "employer_cost"],
        var_name="measure",
        value_name="amount",
    )
    long_costs["measure"] = long_costs["measure"].map(
        {
            "gross_pay": "Gross pay",
            "net_pay": "Net pay",
            "employer_cost": "Employer cost",
        }
    )
    cost_chart = px.line(
        long_costs,
        x="period_start",
        y="amount",
        color="measure",
        markers=True,
        labels={"period_start": "Month", "amount": "INR", "measure": "Measure"},
        color_discrete_map={
            "Gross pay": TEAL,
            "Net pay": "#6B8E23",
            "Employer cost": AMBER,
        },
    )
    cost_chart.update_layout(
        height=360,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_tickprefix="₹",
        legend_title=None,
    )
    st.plotly_chart(cost_chart, width="stretch", config={"displayModeBar": False})

    cost_per_employee_chart = px.line(
        trend,
        x="period_start",
        y="cost_per_employee",
        markers=True,
        labels={
            "period_start": "Month",
            "cost_per_employee": "Employer cost per paid employee (INR)",
        },
    )
    cost_per_employee_chart.update_traces(line_color=TEAL)
    cost_per_employee_chart.update_layout(
        height=300,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_tickprefix="₹",
    )
    st.plotly_chart(
        cost_per_employee_chart,
        width="stretch",
        config={"displayModeBar": False},
    )

    st.subheader(f"Department totals · {month_labels[selected_month]}")
    st.dataframe(
        display_departments[
            [
                "department_name",
                "department_id",
                "group_size",
                "gross_pay",
                "net_pay",
                "employer_cost",
                "cost_per_employee",
            ]
        ].rename(
            columns={
                "department_name": "Department",
                "department_id": "Department ID",
                "group_size": "Paid employees",
                "gross_pay": "Gross pay (INR)",
                "net_pay": "Net pay (INR)",
                "employer_cost": "Employer cost (INR)",
                "cost_per_employee": "Cost per employee (INR)",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"Department groups below {minimum_size} paid employees are suppressed. "
        "The company-wide total is a separate aggregate; department rows may not "
        "sum to it because suppressed groups are omitted."
    )

    with st.expander("Payroll rows excluded from reporting"):
        st.dataframe(
            exclusions.rename(
                columns={
                    "action": "Treatment",
                    "record_id": "Payroll item",
                    "reason": "Reason",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Original payroll source rows are preserved. Exact duplicate employee/run "
            "rows are deduplicated; records without a matching employee dimension row "
            "are excluded from the cleaned reporting feed."
        )


render_payroll_page()
