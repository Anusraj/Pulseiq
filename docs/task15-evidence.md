# Task 15: Executive company-health scorecard

## KPI list and founder rationale

| KPI | Why it belongs on the scorecard |
|---|---|
| Headcount | Shows the scale of the workforce leaders are responsible for. |
| Monthly attrition | Signals whether retention is putting capacity and continuity at risk. |
| Attendance rate | Shows whether planned workforce capacity is showing up to work. |
| Overtime share | Highlights workload pressure and a controllable payroll cost driver. |
| Revenue | Anchors workforce decisions to the income the company is generating. |
| Net profit | Shows whether revenue is converting into cash-generating performance. |
| Operating margin | Shows how much of each revenue rupee remains after operating costs. |
| Net hiring | Shows whether the workforce is expanding or contracting this month. |

The five-KPI alternative removes **Headcount**, **Net hiring**, and **Overtime
share**. Headcount and net hiring overlap on workforce movement, while overtime
share is a diagnostic cost driver better handled on the payroll detail page.
The implemented eight-KPI view retains them because the requested scorecard has
room for eight and the links make the detail available without cluttering the
headline read.

## Traceability and behavior

- Every card is sourced from `metrics.dashboard_executive_scorecard`.
- That view aggregates only governed metric views: M01, M04, M11, M13, M16,
  M17, M18, and M29.
- Attendance, overtime share, and monthly attrition targets and statuses come
  from `metrics.dashboard_kpi_target_status`, which reads `warehouse.kpi_targets`.
- KPIs without a source target show `Target not set` and `NO_TARGET`; no target
  is fabricated.
- Each card includes a working Streamlit link to its detailed page.
- The page has a month selector, two rows of four cards, compact rationale table,
  and A4-landscape print CSS.

## Validation

- `python metrics.py` rebuilt the metric layer and scorecard view.
- `python -m py_compile pages/11_Executive_Scorecard.py` passed.
- The scorecard selector exposes only months with all eight KPI rows; the
  current data has 18 complete months from April 2025 through September 2026.
- Screenshot: [task15-executive-scorecard.png](../task15-executive-scorecard.png).
- `streamlit run app.py` was used for the screenshot evidence:
  `task15-executive-scorecard.png`.
