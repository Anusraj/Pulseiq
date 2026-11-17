"""Budget-versus-actual payroll and KPI target dashboard."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


from release_config import DATABASE
TEAL = "#087E8B"
AMBER = "#D98E32"
RED = "#C2413B"
GREEN = "#24845A"


@st.cache_data(ttl=600, show_spinner=False)
def load_budget_kpi_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        budget = connection.execute("""
            SELECT period_start, department_id, department_name, group_size,
                   budget_payroll_cost, actual_payroll_cost, variance,
                   variance_pct, overspend_rank, traffic_light
            FROM metrics.dashboard_budget_vs_actual
            ORDER BY period_start, overspend_rank, department_id
        """).fetchdf()
        kpis = connection.execute("""
            SELECT period_start, department_id, department_name, kpi_name,
                   group_size, actual_value, target_value, variance_to_target,
                   unit, good_direction, traffic_light
            FROM metrics.dashboard_kpi_target_status
            ORDER BY period_start, department_name, kpi_name
        """).fetchdf()
    finally:
        connection.close()

    budget["period_start"] = pd.to_datetime(budget["period_start"])
    kpis["period_start"] = pd.to_datetime(kpis["period_start"])
    return budget, kpis


def status_label(value: str) -> str:
    return {
        "GREEN": "🟢 On target",
        "AMBER": "🟡 Watch",
        "RED": "🔴 Over target",
        "NO_TARGET": "⚪ No target",
        "NO_REPORTABLE_ACTUAL": "⚪ No reportable actual",
    }.get(value, "⚪ Not available")


def render_budget_kpi_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Budget and KPI targets",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Budget versus actual")
    st.caption(
        "Compare payroll plans with governed actuals, and review department KPIs "
        "against their monthly targets."
    )

    try:
        budget, kpis = load_budget_kpi_data(str(DATABASE))
    except (duckdb.Error, OSError) as exc:
        st.error(
            "Budget and KPI views are not ready. Confirm the two source CSVs are "
            "in `data/raw`, then run `python etl.py`, `python warehouse.py`, "
            "and `python metrics.py`."
        )
        st.exception(exc)
        return

    if budget.empty:
        st.error("No department/month payroll budget groups meet the privacy threshold.")
        return

    months = sorted(budget["period_start"].drop_duplicates().tolist())
    month_labels = {month: month.strftime("%B %Y") for month in months}
    departments = (
        budget[["department_id", "department_name"]]
        .drop_duplicates()
        .sort_values("department_name")
    )
    department_labels = departments.set_index("department_id")["department_name"].to_dict()
    all_departments = "All reportable departments"

    with st.sidebar:
        st.header("Filters")
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
                all_departments
                if value == all_departments
                else f"{department_labels[value]} · {value}"
            ),
        )

    month_budget = budget.loc[budget["period_start"].eq(selected_month)].copy()
    month_kpis = kpis.loc[kpis["period_start"].eq(selected_month)].copy()
    if selected_department != all_departments:
        month_budget = month_budget.loc[
            month_budget["department_id"].eq(selected_department)
        ]
        month_kpis = month_kpis.loc[
            month_kpis["department_id"].eq(selected_department)
        ]
    if month_budget.empty:
        st.info("No reportable payroll actual is available for this filter.")
        return

    total_budget = float(month_budget["budget_payroll_cost"].sum())
    total_actual = float(month_budget["actual_payroll_cost"].sum())
    total_variance = total_actual - total_budget
    variance_pct = 100.0 * total_variance / total_budget if total_budget else 0.0
    cards = st.columns(3)
    cards[0].metric("Reportable budget", f"₹{total_budget:,.0f}")
    cards[1].metric("Reportable actual", f"₹{total_actual:,.0f}")
    cards[2].metric(
        "Variance · actual − budget",
        f"₹{total_variance:,.0f}",
        delta=f"{variance_pct:+.2f}%",
        delta_color="inverse",
    )

    st.info(
        "**Sign rule:** variance = actual payroll cost − budget. Positive means "
        "overspend; negative means underspend. Department groups below five "
        "paid employees are suppressed, so reportable department sums may not "
        "equal the company total."
    )
    st.caption(
        "Payroll traffic lights: green = at or under budget; amber = overspend "
        "up to 5%; red = overspend above 5%. The source provides budget values "
        "but no tolerance bands, so the 5% amber band is an explicit dashboard "
        "review convention—not a source-defined threshold."
    )

    st.subheader(f"Payroll budget ranking · {month_labels[selected_month]}")
    ranked = month_budget.sort_values(
        ["variance", "department_name"], ascending=[False, True]
    ).copy()
    ranked["status_label"] = ranked["traffic_light"].map(status_label)
    ranked_chart = px.bar(
        ranked.sort_values("variance"),
        x="variance",
        y="department_name",
        color="traffic_light",
        orientation="h",
        color_discrete_map={"GREEN": GREEN, "AMBER": AMBER, "RED": RED},
        labels={
            "variance": "Actual − budget (INR)",
            "department_name": "Department",
            "traffic_light": "Status",
        },
        hover_data=["budget_payroll_cost", "actual_payroll_cost", "variance_pct"],
    )
    ranked_chart.add_vline(x=0, line_dash="dash", line_color="#667085")
    ranked_chart.update_layout(
        height=max(350, 42 * len(ranked)),
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_tickprefix="₹",
        showlegend=False,
    )
    st.plotly_chart(ranked_chart, width="stretch", config={"displayModeBar": False})

    st.dataframe(
        ranked[
            [
                "overspend_rank",
                "department_name",
                "group_size",
                "budget_payroll_cost",
                "actual_payroll_cost",
                "variance",
                "variance_pct",
                "status_label",
            ]
        ].rename(
            columns={
                "overspend_rank": "Overspend rank",
                "department_name": "Department",
                "group_size": "Paid employees",
                "budget_payroll_cost": "Budget (INR)",
                "actual_payroll_cost": "Actual (INR)",
                "variance": "Actual − budget (INR)",
                "variance_pct": "Variance (%)",
                "status_label": "Traffic light",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    if selected_department == all_departments:
        trend = budget.groupby("period_start", as_index=False).agg(
            budget_payroll_cost=("budget_payroll_cost", "sum"),
            actual_payroll_cost=("actual_payroll_cost", "sum"),
        )
    else:
        trend = budget.loc[
            budget["department_id"].eq(selected_department),
            ["period_start", "budget_payroll_cost", "actual_payroll_cost"],
        ].copy()
    trend_long = trend.melt(
        id_vars=["period_start"],
        value_vars=["budget_payroll_cost", "actual_payroll_cost"],
        var_name="measure",
        value_name="amount",
    )
    trend_long["measure"] = trend_long["measure"].map(
        {"budget_payroll_cost": "Budget", "actual_payroll_cost": "Actual"}
    )
    st.subheader("Payroll budget and actual trend")
    trend_chart = px.line(
        trend_long,
        x="period_start",
        y="amount",
        color="measure",
        markers=True,
        labels={"period_start": "Month", "amount": "INR", "measure": "Measure"},
        color_discrete_map={"Budget": "#667085", "Actual": TEAL},
    )
    trend_chart.update_layout(
        height=330,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_tickprefix="₹",
        legend_title=None,
    )
    st.plotly_chart(trend_chart, width="stretch", config={"displayModeBar": False})

    st.subheader(f"KPI targets · {month_labels[selected_month]}")
    st.caption(
        "For attendance and task completion, meeting or exceeding the target is "
        "green; overtime and attrition are green at or below target. The target "
        "file defines target values, not tolerance bands, so KPI status is binary: "
        "green or red. Missing targets and suppressed actuals are shown separately."
    )
    with st.expander("KPI formulas and period alignment"):
        st.markdown(
            "- **Attendance:** (present days + 0.5 × unpaid half-days) ÷ "
            "scheduled days. Target is supplied as a fraction and both values "
            "are displayed as percentages.\n"
            "- **Overtime share:** overtime pay ÷ employer payroll cost × 100.\n"
            "- **Monthly attrition:** exits ÷ average of start- and end-month "
            "headcount × 100.\n"
            "- **Task completion:** Done tasks ÷ non-cancelled tasks × 100, "
            "grouped by the department owning the team and the sprint's start "
            "month. Cancelled tasks are excluded; groups below five tasks are "
            "suppressed. This department/month rollup is not a team ranking."
        )
    if month_kpis.empty:
        st.info("No KPI targets are available for this department/month.")
    else:
        month_kpis["traffic_label"] = month_kpis["traffic_light"].map(status_label)
        st.dataframe(
            month_kpis[
                [
                    "kpi_name",
                    "actual_value",
                    "target_value",
                    "variance_to_target",
                    "good_direction",
                    "traffic_label",
                ]
            ].rename(
                columns={
                    "kpi_name": "KPI",
                    "actual_value": "Actual (%)",
                    "target_value": "Target (%)",
                    "variance_to_target": "Actual − target (pp)",
                    "good_direction": "Better direction",
                    "traffic_label": "Traffic light",
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Recommendations")
    positive_variances = ranked.loc[ranked["variance"] > 0].head(2)
    if positive_variances.empty:
        st.markdown(
            "No reportable department is above its payroll budget this month. "
            "Continue monitoring monthly and validate the plan assumptions."
        )
    else:
        for row in positive_variances.itertuples(index=False):
            st.markdown(
                f"- **{row.department_name} (rank {row.overspend_rank}, "
                f"{row.variance_pct:.1f}% over; ₹{row.variance:,.0f}):** "
                "reconcile paid headcount, start dates, overtime and one-off "
                "pay before changing staffing. Confirm whether the budget "
                "reflects the current hiring plan."
            )
    st.caption(
        "If a hiring freeze was introduced after the budget was approved, show "
        "the original approved budget unchanged, annotate the freeze date and "
        "owner, and add a separately versioned revised forecast. Do not silently "
        "rewrite the baseline or attribute all variance to department execution."
    )


render_budget_kpi_page()
