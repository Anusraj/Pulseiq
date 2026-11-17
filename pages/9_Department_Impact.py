"""Cross-department cost, attendance, leave, and attrition dashboard."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


from release_config import DATABASE
TEAL = "#087E8B"
AMBER = "#D98E32"
RED = "#C2413B"


@st.cache_data(ttl=600, show_spinner=False)
def load_impact_data(database_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        impact = connection.execute(
            """
            SELECT period_start, department_id, department_name,
                   headcount_end, hires, exits, attrition_rate,
                   employees_paid, employer_cost, gross_pay, overtime_pay,
                   overtime_hours, cost_per_head, overtime_share_pct,
                   attendance_rate_pct, approved_leave_days,
                   approved_leave_days_per_head, overtime_cost_per_paid_head
            FROM metrics.dashboard_department_impact
            ORDER BY period_start, department_name
            """
        ).fetchdf()
        reconciliation = connection.execute(
            """
            SELECT * FROM metrics.dashboard_department_impact_reconciliation
            ORDER BY period_start, department_name
            """
        ).fetchdf()
    finally:
        connection.close()
    impact["period_start"] = pd.to_datetime(impact["period_start"])
    reconciliation["period_start"] = pd.to_datetime(reconciliation["period_start"])
    return impact, reconciliation


def display_value(value: object, suffix: str = "", decimals: int = 0) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}{suffix}"


def money(value: object) -> str:
    if pd.isna(value):
        return "—"
    return f"₹{float(value):,.0f}"


def sum_display(values: pd.Series, suffix: str = "", decimals: int = 0) -> str:
    if values.dropna().empty:
        return "—"
    return display_value(values.sum(), suffix=suffix, decimals=decimals)


def render_department_impact_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Department impact",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Cross-department impact")
    st.caption(
        "One department-month grain connects headcount, payroll, attendance, "
        "overtime, approved leave, and attrition."
    )

    try:
        impact, reconciliation = load_impact_data(str(DATABASE))
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "Department impact views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if impact.empty:
        st.error("No department-month rows are available.")
        return

    months = sorted(impact["period_start"].drop_duplicates().tolist())
    month_labels = {month: month.strftime("%B %Y") for month in months}
    departments = (
        impact[["department_id", "department_name"]]
        .drop_duplicates()
        .sort_values("department_name")
    )
    department_labels = departments.set_index("department_id")["department_name"].to_dict()
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
            [all_departments, *departments["department_id"].tolist()],
            format_func=lambda value: (
                all_departments if value == all_departments
                else f"{department_labels[value]} · {value}"
            ),
        )

    selected_rows = impact.loc[impact["period_start"].eq(selected_month)].copy()
    if selected_department != all_departments:
        selected_rows = selected_rows.loc[
            selected_rows["department_id"].eq(selected_department)
        ]
    if selected_rows.empty:
        st.info("No department-month row is available for this filter.")
        return
    chart_rows = selected_rows.dropna(
        subset=["employer_cost", "attrition_rate", "overtime_pay"]
    ).copy()

    if selected_department == all_departments:
        cards = st.columns(4)
        cards[0].metric("Employer cost", sum_display(selected_rows["employer_cost"], ""))
        cards[1].metric("Paid employees", sum_display(selected_rows["employees_paid"]))
        cards[2].metric("Overtime pay", sum_display(selected_rows["overtime_pay"], ""))
        cards[3].metric(
            "Approved leave days",
            sum_display(selected_rows["approved_leave_days"], decimals=1),
        )
    else:
        row = selected_rows.iloc[0]
        cards = st.columns(4)
        cards[0].metric("Employer cost", money(row["employer_cost"]))
        cards[1].metric("Paid employees", display_value(row["employees_paid"]))
        cards[2].metric("Overtime pay", money(row["overtime_pay"]))
        cards[3].metric(
            "Attrition",
            display_value(row["attrition_rate"], suffix="%", decimals=2),
        )

    st.info(
        "Join order: aggregate each fact independently to department × month, "
        "then join the aggregates. This avoids multiplying payroll rows by "
        "attendance or leave rows. Leave additions are approved leave days and "
        "leave days per head; the reference summary has no leave columns."
    )

    st.subheader(f"Department comparison · {month_labels[selected_month]}")
    if chart_rows.empty:
        st.info("No payroll measures are available for this department-month.")
    else:
        chart_rows = chart_rows.sort_values("employer_cost").copy()
        chart_rows["attrition_label"] = chart_rows["attrition_rate"].map(
            lambda value: f"{value:.2f}% attrition"
        )
        chart = px.bar(
            chart_rows,
            x="employer_cost",
            y="department_name",
            orientation="h",
            color="attrition_rate",
            text="attrition_label",
            color_continuous_scale=[TEAL, AMBER, RED],
            hover_data=[
                "attrition_rate",
                "employees_paid",
                "overtime_pay",
                "overtime_hours",
                "approved_leave_days_per_head",
                "attendance_rate_pct",
            ],
            labels={
                "employer_cost": "Employer cost (INR)",
                "department_name": "Department",
                "attrition_rate": "Attrition (%)",
                "overtime_pay": "Overtime pay (INR)",
            },
        )
        chart.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Employer cost: ₹%{x:,.0f}<br>"
                "Attrition: %{customdata[0]:.2f}%<br>"
                "Paid employees: %{customdata[1]:,.0f}<br>"
                "Overtime pay: ₹%{customdata[2]:,.0f}<br>"
                "Overtime hours: %{customdata[3]:,.1f}<br>"
                "Leave days/head: %{customdata[4]:,.2f}<br>"
                "Attendance: %{customdata[5]:,.2f}%<extra></extra>"
            ),
        )
        chart.update_layout(
            height=460,
            margin=dict(l=8, r=80, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickprefix="₹",
            coloraxis_colorbar_title="Attrition %",
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})

    st.subheader("Combined department-month table")
    display = selected_rows[
        [
            "department_name", "headcount_end", "employees_paid", "employer_cost",
            "overtime_pay", "overtime_hours", "attrition_rate", "attendance_rate_pct",
            "approved_leave_days", "approved_leave_days_per_head", "cost_per_head",
        ]
    ].rename(
        columns={
            "department_name": "Department",
            "headcount_end": "Headcount",
            "employees_paid": "Paid employees",
            "employer_cost": "Employer cost (INR)",
            "overtime_pay": "Overtime pay (INR)",
            "overtime_hours": "Overtime hours",
            "attrition_rate": "Attrition (%)",
            "attendance_rate_pct": "Attendance (%)",
            "approved_leave_days": "Approved leave days",
            "approved_leave_days_per_head": "Leave days per head",
            "cost_per_head": "Cost per head (INR)",
        }
    )
    st.dataframe(
        display.style.format(
            {
                "Employer cost (INR)": "{:,.2f}",
                "Overtime pay (INR)": "{:,.2f}",
                "Overtime hours": "{:,.2f}",
                "Attrition (%)": "{:,.2f}",
                "Attendance (%)": "{:,.2f}",
                "Approved leave days": "{:,.2f}",
                "Leave days per head": "{:,.2f}",
                "Cost per head (INR)": "{:,.2f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Reference-summary reconciliation")
    selected_recon = reconciliation.loc[
        reconciliation["period_start"].eq(selected_month)
    ].copy()
    recon_columns = [
        "department_id", "department_name", "employer_cost_difference",
        "gross_pay_difference", "overtime_pay_difference",
        "attendance_rate_difference", "attrition_rate_difference",
        "cost_per_head_difference", "overtime_share_difference",
    ]
    st.dataframe(
        selected_recon[recon_columns].rename(
            columns={
                "department_id": "Department ID",
                "department_name": "Department",
                "employer_cost_difference": "Employer cost diff",
                "gross_pay_difference": "Gross pay diff",
                "overtime_pay_difference": "Overtime pay diff",
                "attendance_rate_difference": "Attendance diff (pp)",
                "attrition_rate_difference": "Attrition diff (pp)",
                "cost_per_head_difference": "Cost/head diff",
                "overtime_share_difference": "OT share diff (pp)",
            }
        ).style.format(
            {
                "Employer cost diff": "{:,.2f}",
                "Gross pay diff": "{:,.2f}",
                "Overtime pay diff": "{:,.2f}",
                "Attendance diff (pp)": "{:,.2f}",
                "Attrition diff (pp)": "{:,.2f}",
                "Cost/head diff": "{:,.2f}",
                "OT share diff (pp)": "{:,.2f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Differences should be zero apart from documented source-quality issues. "
        "The reference reconciliation is shown at the same department-month grain."
    )

    st.subheader("Interpretation")
    st.markdown(
        """
        High overtime and high attrition do not prove that overtime causes
        attrition. Other explanations include understaffing, seasonal demand,
        difficult projects, poor scheduling, manager or role mix, and reverse
        causality where attrition creates overtime for the remaining team.
        Check overtime by role, vacancy and hiring timing, workload, manager,
        tenure, and exit reason before making a causal claim.
        """
    )


if __name__ == "__main__":
    render_department_impact_page()
