# Task 7: attrition analytics

## Page and metric sources

The **Attrition** page is available from Streamlit's multipage navigation.
Actual exits, monthly attrition rates, and predicted high-risk share come from
the governed `metrics.m03_exits`, `metrics.m04_attrition_rate_monthly`, and
`metrics.m27_high_risk_share` views. Supporting views in `metric_views.sql`
provide reportable monthly department exits, voluntary/other exit totals, and
tenure-at-exit groups.

The page's actual section has department and date-range filters. The prediction
section is separate, labelled **Predicted, not certain**, and always shows the
latest available prediction snapshot date rather than implying it is a
forecast for the selected actual period.

## Findings

For the default actual reporting period, October 2025 through September 2026:

1. **October 2025 had the most exits:** 10 across the department/month groups
   reported by the governed M03 view.
2. **Engineering (D01) had the most exits by department:** 21 during the
   selected 12-month period.
3. **Customer Support (D06) had the largest predicted high-risk share:** 34.48%
   of its 58-person reportable group (20 people) in the latest snapshot dated
   September 30, 2026.

Counts are those returned by the metric views; group suppression can make
breakdown totals lower than unsuppressed company totals.

## Privacy and interpretation

- M03 suppresses department/month groups below five people.
- The voluntary/other comparison is all available history and is displayed
  only when both exit categories for a department meet the five-person
  minimum.
- Tenure at exit is calculated from hire date to last working day. The
  department/tenure groups use M04's ten-person minimum.
- M27 suppresses prediction groups below ten people. A four-person department
  is omitted rather than shown as a percentage.
- No employee names, identifiers, or individual risk scores are queried by the
  page.
- A predicted risk is a model estimate for an aggregate group, not a confirmed
  future exit, an individual finding, or a decision rule. Use it to guide
  supportive review; consider model freshness and fairness.

## Screenshot evidence

Capture the rendered Attrition page as `docs/task7-attrition-dashboard.png`
after opening the app in an organization-approved Streamlit environment. The
local machine currently reports that Application Control blocks the
`streamlit.exe` launcher, so no rendered screenshot is included with this
change.

## Validation

- `python metrics.py` rebuilt all 29 official metric views; all view privacy
  checks and six hand checks passed.
- The supporting attrition views were checked against M03/M27 and their
  applicable minimum group sizes.
- `python -m py_compile pages/3_Attrition.py` passed.
