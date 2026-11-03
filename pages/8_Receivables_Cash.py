"""Receivables ageing, client payment behaviour, and cash-flow dashboard."""

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
def load_receivables_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        ageing = connection.execute(
            """
            SELECT ageing_bucket, invoice_count, open_receivables,
                   oldest_days_past_due
            FROM metrics.dashboard_receivables_ageing
            ORDER BY CASE ageing_bucket
                WHEN '0-30 days' THEN 1
                WHEN '31-60 days' THEN 2
                WHEN '61-90 days' THEN 3
                ELSE 4 END
            """
        ).fetchdf()
        summary = connection.execute(
            """
            SELECT as_of_date, open_invoice_count, total_open_receivables
            FROM metrics.dashboard_receivables_summary
            """
        ).fetchdf()
        overdue_clients = connection.execute(
            """
            SELECT client_id, client_name, overdue_invoice_count,
                   overdue_receivables, oldest_days_past_due
            FROM metrics.dashboard_overdue_clients
            ORDER BY overdue_receivables DESC, client_name
            """
        ).fetchdf()
        client_days = connection.execute(
            """
            SELECT client_id, client_name, payment_terms_days,
                   payment_behaviour, paid_invoice_count,
                   average_days_to_pay, average_days_over_terms
            FROM metrics.dashboard_client_days_to_pay
            ORDER BY average_days_to_pay DESC, client_name
            """
        ).fetchdf()
        cash_flow = connection.execute(
            """
            SELECT period_start, cash_in, cash_out, net_cash_flow
            FROM metrics.dashboard_cash_flow_monthly
            ORDER BY period_start
            """
        ).fetchdf()
    finally:
        connection.close()

    cash_flow["period_start"] = pd.to_datetime(cash_flow["period_start"])
    return ageing, summary, overdue_clients, client_days, cash_flow


def money(value: float) -> str:
    return f"₹{value:,.0f}"


def render_receivables_cash_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Receivables and cash",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Receivables and cash")
    st.caption(
        "Prioritise open customer balances, understand payment behaviour, and "
        "compare cash collected with paid expense bills."
    )

    try:
        ageing, summary, overdue_clients, client_days, cash_flow = load_receivables_data(
            str(DATABASE)
        )
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "Receivables metric views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if summary.empty:
        st.error("No open receivables are available.")
        return

    as_of_date = summary.iloc[0]["as_of_date"]
    total_open = float(summary.iloc[0]["total_open_receivables"])
    open_invoice_count = int(summary.iloc[0]["open_invoice_count"])
    cards = st.columns(3)
    cards[0].metric("Open receivables", money(total_open))
    cards[1].metric("Open invoices", f"{open_invoice_count:,}")
    cards[2].metric("As of", pd.Timestamp(as_of_date).strftime("%d %b %Y"))

    st.info(
        "**Open statuses:** only SENT, OVERDUE and PARTIALLY_PAID are included. "
        "Ageing is days past due as of the latest invoice date; invoices not yet "
        "due are placed in 0–30 days. PAID, DRAFT and CANCELLED are excluded."
    )

    st.subheader("Receivables ageing")
    ageing_total = float(ageing["open_receivables"].sum())
    st.bar_chart(
        ageing.set_index("ageing_bucket")["open_receivables"],
        color=TEAL,
        horizontal=True,
    )
    st.dataframe(
        ageing.rename(
            columns={
                "ageing_bucket": "Ageing bucket",
                "invoice_count": "Invoices",
                "open_receivables": "Open receivables (INR)",
                "oldest_days_past_due": "Oldest days past due",
            }
        ).style.format({"Open receivables (INR)": "{:,.2f}"}),
        hide_index=True,
        width="stretch",
    )
    if abs(ageing_total - total_open) <= 0.01:
        st.success(
            f"Bucket total checks: {money(ageing_total)} = total open receivables "
            f"{money(total_open)}."
        )
    else:
        st.error(
            f"Bucket total does not tie: {money(ageing_total)} versus "
            f"{money(total_open)}."
        )

    left, right = st.columns(2)
    with left:
        st.subheader("Clients with most overdue money")
        top_overdue = overdue_clients.head(10).sort_values("overdue_receivables")
        overdue_chart = px.bar(
            top_overdue,
            x="overdue_receivables",
            y="client_name",
            orientation="h",
            color_discrete_sequence=[RED],
            labels={
                "overdue_receivables": "Overdue receivables (INR)",
                "client_name": "Client",
            },
            hover_data=["overdue_invoice_count", "oldest_days_past_due"],
        )
        overdue_chart.update_layout(
            height=440,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickprefix="₹",
        )
        st.plotly_chart(overdue_chart, width="stretch", config={"displayModeBar": False})

    with right:
        st.subheader("Average days to pay by client")
        slow_clients = client_days.head(10).sort_values("average_days_to_pay")
        days_chart = px.bar(
            slow_clients,
            x="average_days_to_pay",
            y="client_name",
            orientation="h",
            color="average_days_over_terms",
            color_continuous_scale=[GREEN, AMBER, RED],
            labels={
                "average_days_to_pay": "Average days to pay",
                "client_name": "Client",
                "average_days_over_terms": "Days over terms",
            },
            hover_data=["payment_terms_days", "paid_invoice_count"],
        )
        days_chart.update_layout(
            height=440,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(days_chart, width="stretch", config={"displayModeBar": False})

    st.dataframe(
        client_days.rename(
            columns={
                "client_name": "Client",
                "payment_terms_days": "Terms (days)",
                "payment_behaviour": "Source behaviour",
                "paid_invoice_count": "Paid invoices",
                "average_days_to_pay": "Average days to pay",
                "average_days_over_terms": "Average days over terms",
            }
        ).style.format(
            {
                "Average days to pay": "{:,.2f}",
                "Average days over terms": "{:,.2f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Cash in versus cash out")
    st.caption(
        "Cash in is recorded invoice payments. Cash out is paid expense bills "
        "using total bill value including GST, grouped by the payment date."
    )
    cash_long = cash_flow.melt(
        id_vars=["period_start"],
        value_vars=["cash_in", "cash_out"],
        var_name="measure",
        value_name="amount",
    )
    cash_long["measure"] = cash_long["measure"].map(
        {"cash_in": "Cash in", "cash_out": "Cash out"}
    )
    cash_chart = px.bar(
        cash_long,
        x="period_start",
        y="amount",
        color="measure",
        barmode="group",
        color_discrete_map={"Cash in": TEAL, "Cash out": AMBER},
        labels={"period_start": "Month", "amount": "INR", "measure": "Measure"},
    )
    cash_chart.add_scatter(
        x=cash_flow["period_start"],
        y=cash_flow["net_cash_flow"],
        name="Net cash flow",
        mode="lines+markers",
        yaxis="y2",
        line={"color": GREEN, "width": 3},
    )
    cash_chart.update_layout(
        height=420,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"title": "INR", "tickprefix": "₹"},
        yaxis2={"title": "Net cash flow", "overlaying": "y", "side": "right"},
        legend={"orientation": "h", "y": 1.08},
    )
    st.plotly_chart(cash_chart, width="stretch", config={"displayModeBar": False})

    st.subheader("Collections questions")
    st.markdown(
        """
- A big client that always pays at 75 days is a risk if its terms are 30 or
  45 days: it creates a predictable funding gap and concentration exposure.
- Ask Finance whether the 75-day pattern is contractually approved, whether
  credit limits and collections escalation reflect the behaviour, and whether
  the client has recently increased its overdue balance or disputed invoices.
        """
    )


if __name__ == "__main__":
    render_receivables_cash_page()
