"""AI anomaly, forecast, and attrition-risk signals dashboard."""

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
def load_ai_signals_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        anomalies = connection.execute(
            """
            SELECT reason_code, anomaly_count, money_at_risk,
                   average_anomaly_score, latest_period, example_reason
            FROM metrics.dashboard_ai_anomaly_summary
            ORDER BY money_at_risk DESC, reason_code
            """
        ).fetchdf()
        forecasts = connection.execute(
            """
            SELECT forecast_id, period_start, department_id, forecast_value,
                   lower_80, upper_80, actual, actual_status,
                   absolute_error, error_pct, method, trained_through,
                   model_version
            FROM metrics.dashboard_ai_forecast
            WHERE department_id = 'ALL'
            ORDER BY period_start
            """
        ).fetchdf()
        risk = connection.execute(
            """
            SELECT as_of_date, risk_band, employee_count, average_risk_pct
            FROM metrics.dashboard_ai_attrition_risk_summary
            ORDER BY as_of_date, CASE risk_band
                WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
            """
        ).fetchdf()
    finally:
        connection.close()

    forecasts["period_start"] = pd.to_datetime(forecasts["period_start"])
    anomalies["latest_period"] = pd.to_datetime(anomalies["latest_period"])
    risk["as_of_date"] = pd.to_datetime(risk["as_of_date"])
    return anomalies, forecasts, risk


def money(value: object) -> str:
    if pd.isna(value):
        return "—"
    return f"₹{float(value):,.0f}"


def render_ai_signals_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | AI signals",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("AI signals")
    st.caption(
        "Anomalies, headcount forecasts, and attrition-risk signals are model "
        "outputs for human review, not automated decisions."
    )

    try:
        anomalies, forecasts, risk = load_ai_signals_data(str(DATABASE))
    except (duckdb.Error, OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(
            "AI signal views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py`."
        )
        st.exception(exc)
        return

    if anomalies.empty or forecasts.empty:
        st.error("AI signal data is not available.")
        return

    known_errors = forecasts.loc[forecasts["error_pct"].notna(), "error_pct"]
    cards = st.columns(4)
    cards[0].metric("Flagged anomaly types", f"{len(anomalies):,}")
    cards[1].metric(
        "Money at risk",
        money(anomalies["money_at_risk"].sum()),
    )
    cards[2].metric(
        "Known-month MAPE",
        "—" if known_errors.empty else f"{known_errors.mean():.2f}%",
    )
    high_risk = risk.loc[risk["risk_band"].eq("High"), "employee_count"].sum()
    cards[3].metric("High attrition-risk employees", f"{int(high_risk):,}")

    st.warning(
        "AI-generated outputs are directional signals for human review. "
        "They do not prove misconduct, predict an individual's decision, or "
        "guarantee a future result."
    )

    st.subheader("Anomalies by type and money at risk")
    st.caption("AI-generated, for human review")
    st.info(
        "Start with the largest bars: money at risk is the supplied model "
        "estimate attached to flagged records, not confirmed financial loss."
    )
    anomaly_chart = px.bar(
        anomalies.sort_values("money_at_risk"),
        x="money_at_risk",
        y="reason_code",
        orientation="h",
        color="money_at_risk",
        color_continuous_scale=[TEAL, AMBER, RED],
        hover_data=["anomaly_count", "average_anomaly_score", "example_reason"],
        labels={
            "money_at_risk": "Money at risk (INR)",
            "reason_code": "Anomaly type",
            "anomaly_count": "Flagged records",
        },
    )
    anomaly_chart.update_layout(
        height=500,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_tickprefix="₹",
        coloraxis_showscale=False,
    )
    st.plotly_chart(anomaly_chart, width="stretch", config={"displayModeBar": False})
    st.dataframe(
        anomalies.rename(
            columns={
                "reason_code": "Anomaly type",
                "anomaly_count": "Flagged records",
                "money_at_risk": "Money at risk (INR)",
                "average_anomaly_score": "Average score",
                "latest_period": "Latest period",
                "example_reason": "Example reason",
            }
        ).style.format(
            {
                "Money at risk (INR)": "{:,.2f}",
                "Average score": "{:.3f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Headcount forecast versus actual")
    st.caption("AI-generated, for human review")
    st.info(
        "The line is the model forecast and the shaded area is its 80% "
        "confidence range. Actuals appear only after a month closes; the "
        "forecast is not a promise."
    )
    forecast_chart = px.line(
        forecasts,
        x="period_start",
        y="forecast_value",
        markers=True,
        labels={"period_start": "Month", "forecast_value": "Headcount"},
    )
    forecast_chart.update_traces(
        name="Forecast",
        line={"color": TEAL, "width": 3},
        showlegend=True,
    )
    forecast_chart.add_scatter(
        x=forecasts["period_start"],
        y=forecasts["upper_80"],
        mode="lines",
        line={"color": "rgba(8,126,139,0)"},
        name="80% upper bound",
        showlegend=False,
        hoverinfo="skip",
    )
    forecast_chart.add_scatter(
        x=forecasts["period_start"],
        y=forecasts["lower_80"],
        mode="lines",
        line={"color": "rgba(8,126,139,0)"},
        fill="tonexty",
        fillcolor="rgba(8,126,139,0.18)",
        name="80% confidence band",
        hoverinfo="skip",
    )
    known = forecasts.loc[forecasts["actual"].notna()]
    if not known.empty:
        forecast_chart.add_scatter(
            x=known["period_start"],
            y=known["actual"],
            mode="lines+markers",
            name="Actual",
            line={"color": RED, "width": 3},
        )
    forecast_chart.update_layout(
        height=440,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Headcount",
        legend={"orientation": "h", "y": 1.08},
    )
    st.plotly_chart(forecast_chart, width="stretch", config={"displayModeBar": False})
    if known.empty:
        st.info(
            "No known actual months overlap this forecast horizon. "
            "Forecast error will be calculated here when actuals arrive."
        )
    else:
        st.success(
            f"Known-month MAPE is {known['error_pct'].mean():.2f}% across "
            f"{len(known):,} month(s)."
        )

    error_table = forecasts[
        [
            "period_start",
            "forecast_value",
            "lower_80",
            "upper_80",
            "actual",
            "absolute_error",
            "error_pct",
            "actual_status",
        ]
    ].rename(
        columns={
            "period_start": "Month",
            "forecast_value": "Forecast",
            "lower_80": "80% lower",
            "upper_80": "80% upper",
            "actual": "Actual",
            "absolute_error": "Absolute error",
            "error_pct": "Error (%)",
            "actual_status": "Status",
        }
    )
    st.subheader("Forecast error table")
    st.dataframe(
        error_table.style.format(
            {
                "Forecast": "{:,.1f}",
                "80% lower": "{:,.1f}",
                "80% upper": "{:,.1f}",
                "Actual": "{:,.1f}",
                "Absolute error": "{:,.1f}",
                "Error (%)": "{:.2f}%",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Attrition-risk model output")
    st.caption("AI-generated, for human review")
    st.info(
        "Risk bands help prioritise a conversation; they are not a verdict "
        "about an employee and must not be used as an automated decision."
    )
    risk_chart = px.bar(
        risk.sort_values("employee_count"),
        x="employee_count",
        y="risk_band",
        orientation="h",
        color="risk_band",
        color_discrete_map={"Low": GREEN, "Medium": AMBER, "High": RED},
        labels={"employee_count": "Employees", "risk_band": "Risk band"},
        hover_data=["average_risk_pct"],
    )
    risk_chart.update_layout(
        height=300,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(risk_chart, width="stretch", config={"displayModeBar": False})


if __name__ == "__main__":
    render_ai_signals_page()
