"""Ledger P&L and expense analytics dashboard."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pulseiq.duckdb"
TEAL = "#087E8B"
AMBER = "#D98E32"
RED = "#C2413B"
GREEN = "#24845A"


@st.cache_data(ttl=600, show_spinner=False)
def load_pnl_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        pnl = connection.execute(
            """
            SELECT period_start, revenue, operating_revenue, other_income,
                   expenses, net_profit, operating_margin
            FROM metrics.dashboard_pnl_monthly
            ORDER BY period_start
            """
        ).fetchdf()
        categories = connection.execute(
            """
            SELECT period_start, category, bill_count, spend_excl_gst
            FROM metrics.dashboard_expense_category_monthly
            ORDER BY period_start, spend_excl_gst DESC, category
            """
        ).fetchdf()
        vendors = connection.execute(
            """
            SELECT period_start, vendor_id, vendor_name, bill_count, spend_excl_gst
            FROM metrics.dashboard_expense_vendor_monthly
            ORDER BY period_start, spend_excl_gst DESC, vendor_name
            """
        ).fetchdf()
        tieout = connection.execute(
            """
            SELECT period_start, revenue, expenses, net_profit,
                   headline_revenue, headline_expenses, headline_net_profit,
                   revenue_difference, expense_difference, profit_difference
            FROM metrics.dashboard_pnl_tieout
            ORDER BY period_start
            """
        ).fetchdf()
    finally:
        connection.close()

    for frame in (pnl, categories, vendors, tieout):
        frame["period_start"] = pd.to_datetime(frame["period_start"])
    return pnl, categories, vendors, tieout


def money(value: float) -> str:
    return f"₹{value:,.0f}"


def render_profit_loss_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Profit and loss",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Profit and loss")
    st.caption(
        "Ledger revenue, detail-account expenses and margin by month, with "
        "category and vendor bill-spend analysis."
    )

    try:
        pnl, categories, vendors, tieout = load_pnl_data(str(DATABASE))
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "P&L metric views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if pnl.empty:
        st.error("No P&L months are available.")
        return

    months = pnl["period_start"].tolist()
    month_labels = {month: month.strftime("%B %Y") for month in months}
    with st.sidebar:
        st.header("Report filters")
        selected_month = st.selectbox(
            "Month",
            months,
            index=len(months) - 1,
            format_func=lambda value: month_labels[value],
        )

    selected = pnl.loc[pnl["period_start"].eq(selected_month)].iloc[0]
    month_categories = categories.loc[
        categories["period_start"].eq(selected_month)
    ].copy()
    month_vendors = vendors.loc[vendors["period_start"].eq(selected_month)].copy()
    selected_tieout = tieout.loc[tieout["period_start"].eq(selected_month)].iloc[0]

    cards = st.columns(4)
    cards[0].metric("Revenue", money(selected["revenue"]))
    cards[1].metric("Expenses", money(selected["expenses"]))
    cards[2].metric("Net profit", money(selected["net_profit"]))
    cards[3].metric("Operating margin", f"{selected['operating_margin']:.2f}%")

    st.info(
        "P&L uses ledger detail accounts only: group headings 4000 Income and "
        "5000 Expenses are excluded. Revenue includes detail income account 4900 "
        "Other Income, matching the README headline. Category and vendor charts "
        "use approved expense bills excluding GST and are not added to ledger P&L."
    )

    st.subheader("Monthly revenue, expense and margin")
    trend = pnl.melt(
        id_vars=["period_start"],
        value_vars=["revenue", "expenses", "net_profit"],
        var_name="measure",
        value_name="amount",
    )
    trend["measure"] = trend["measure"].map(
        {"revenue": "Revenue", "expenses": "Expenses", "net_profit": "Net profit"}
    )
    trend_chart = px.bar(
        trend,
        x="period_start",
        y="amount",
        color="measure",
        barmode="group",
        color_discrete_map={"Revenue": TEAL, "Expenses": RED, "Net profit": GREEN},
        labels={"period_start": "Month", "amount": "INR", "measure": "Measure"},
    )
    trend_chart.add_scatter(
        x=pnl["period_start"],
        y=pnl["operating_margin"],
        name="Margin %",
        mode="lines+markers",
        yaxis="y2",
        line={"color": AMBER, "width": 3},
    )
    trend_chart.update_layout(
        height=420,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"title": "INR", "tickprefix": "₹"},
        yaxis2={
            "title": "Margin %",
            "overlaying": "y",
            "side": "right",
            "ticksuffix": "%",
        },
        legend={"orientation": "h", "y": 1.08},
    )
    st.plotly_chart(trend_chart, width="stretch", config={"displayModeBar": False})

    st.subheader(f"P&L table · {month_labels[selected_month]}")
    pnl_table = pd.DataFrame(
        {
            "Line": ["Revenue", "Expenses", "Net profit", "Operating margin"],
            "Amount": [
                selected["revenue"],
                selected["expenses"],
                selected["net_profit"],
                selected["operating_margin"],
            ],
            "Unit": ["INR", "INR", "INR", "%"],
        }
    )
    st.dataframe(
        pnl_table.style.format(
            {"Amount": lambda value: f"{value:,.2f}"}
        ),
        hide_index=True,
        width="stretch",
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Expense by category")
        category_chart = px.bar(
            month_categories.sort_values("spend_excl_gst"),
            x="spend_excl_gst",
            y="category",
            orientation="h",
            color_discrete_sequence=[TEAL],
            labels={"spend_excl_gst": "Spend ex-GST (INR)", "category": "Category"},
            hover_data=["bill_count"],
        )
        category_chart.update_layout(
            height=460,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickprefix="₹",
        )
        st.plotly_chart(category_chart, width="stretch", config={"displayModeBar": False})

    with right:
        st.subheader("Top 10 vendors")
        top_vendors = month_vendors.nlargest(10, "spend_excl_gst").sort_values(
            "spend_excl_gst"
        )
        vendor_chart = px.bar(
            top_vendors,
            x="spend_excl_gst",
            y="vendor_name",
            orientation="h",
            color_discrete_sequence=[AMBER],
            labels={"spend_excl_gst": "Spend ex-GST (INR)", "vendor_name": "Vendor"},
            hover_data=["bill_count"],
        )
        vendor_chart.update_layout(
            height=460,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickprefix="₹",
        )
        st.plotly_chart(vendor_chart, width="stretch", config={"displayModeBar": False})

    st.subheader("README headline tie-out")
    tieout_table = tieout[
        [
            "period_start",
            "revenue",
            "headline_revenue",
            "expenses",
            "headline_expenses",
            "net_profit",
            "headline_net_profit",
            "profit_difference",
        ]
    ].copy()
    tieout_table["period_start"] = tieout_table["period_start"].dt.strftime("%b %Y")
    st.dataframe(
        tieout_table.rename(
            columns={
                "period_start": "Month",
                "revenue": "P&L revenue",
                "headline_revenue": "README revenue",
                "expenses": "P&L expenses",
                "headline_expenses": "README expenses",
                "net_profit": "P&L profit",
                "headline_net_profit": "README profit",
                "profit_difference": "Profit difference",
            }
        ).style.format(
            {
                "P&L revenue": "{:,.2f}",
                "README revenue": "{:,.2f}",
                "P&L expenses": "{:,.2f}",
                "README expenses": "{:,.2f}",
                "P&L profit": "{:,.2f}",
                "README profit": "{:,.2f}",
                "Profit difference": "{:,.2f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    if abs(float(selected_tieout["profit_difference"])) <= 0.01:
        st.success(
            f"{month_labels[selected_month]} ties to the README headline: "
            "revenue, expenses and profit difference are all ₹0.00."
        )
    else:
        st.error("The selected month does not tie to the README headline.")

    st.subheader("Three findings and proof needed")
    st.markdown(
        """
1. **Non-payroll costs may be rising faster than revenue:** prove it by comparing
   the monthly ledger expense trend with the category view, then inspect the
   categories with the largest month-on-month increases.
2. **Payroll mix or headcount growth may be absorbing revenue:** prove it by
   joining the governed payroll-cost view to monthly revenue and checking
   payroll as a percentage of revenue, headcount and cost per head.
3. **A concentrated vendor spike may be leaking margin:** prove it by ranking
   vendors and categories by ex-GST bill spend, then compare the largest
   increases with contract terms, purchase volumes and ledger postings.
        """
    )


if __name__ == "__main__":
    render_profit_loss_page()
