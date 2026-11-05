# Task 14: AI signals dashboard

## What the page shows

The [AI signals page](../pages/10_AI_Signals.py) contains three model-output
surfaces:

- Flagged anomalies are grouped by `reason_code` and ranked by the supplied
  `money_at_risk` amount, largest first. The table keeps the record count,
  average anomaly score, latest period and an example reason visible.
- Company headcount forecasts show the forecast line and the supplied 80%
  confidence band. Actuals are overlaid only when the forecast month has a
  matching closed-month headcount value.
- Attrition-risk bands are shown as a prioritisation aid, not a personnel
  decision. Every chart is labelled **AI-generated, for human review**.

The page also includes a forecast error table with forecast, confidence limits,
actual, absolute error, percentage error and status.

## Forecast error evidence

The supplied forecast horizon is October 2026 through March 2027, while the
latest available actual headcount month is September 2026. Therefore no
forecast month currently has a known actual:

| Forecast months | Known actual months | Known-month MAPE |
|---:|---:|---:|
| 6 | 0 | Not available |

The SQL view calculates absolute percentage error as
`100 × abs(forecast - actual) / actual` whenever `actual` is present. The page
shows `AWAITING_ACTUAL` rather than treating a missing actual as zero. When
months close, the known-month MAPE card and table will populate automatically.

## Plain-language interpretation

Money at risk is a model estimate attached to flagged records, not confirmed
loss. A confidence band is a range of plausible outcomes, not a promise. A
12% error can only be judged with context such as the forecast horizon, business
volatility, baseline comparison, and the cost of being wrong; this dataset does
not support calling 12% good or bad.

## Validation

- `python metrics.py` rebuilt the metric layer and AI dashboard views.
- `python -m py_compile pages/10_AI_Signals.py` passed.
- The page includes an explicit forecast error table and all AI chart labels.
- No commit or push was made for Task 14.
