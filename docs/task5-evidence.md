# Task 5: workforce dashboard

## Five CEO questions

1. How many people are in departments large enough to report safely?
2. Is reportable headcount growing or shrinking over the selected period?
3. Which departments make up the largest share of the workforce?
4. How does reportable headcount divide across city tiers?
5. What is the reported work-mode mix?

## Evidence

Run the app with `streamlit run app.py`. The dashboard reads only the official
`metrics.m01_headcount`, `metrics.m02_hires`, `metrics.m03_exits`, and
`metrics.m29_net_hiring` views,
plus metric-layer views for the department labels and suppressed workforce
breakdowns. No raw or warehouse table is queried by the app.

The headcount KPIs follow M01's minimum group size of five. Location-tier and
work-mode breakdowns apply the same threshold at their own category grain, so
small groups are intentionally omitted. Their category totals may therefore
be lower than reportable department headcount.

The dashboard uses a refreshed, responsive layout while retaining its five
workforce KPIs and charts. Paired "From" and "Through" month selectors allow
selection across every available M01 month, default to the latest 12 available
months, and show the full available date range in the sidebar.

Screenshots: `task5-workforce-dashboard.png` (summary and trend) and
`task5-workforce-breakdowns.png` (department mix).

## Mini challenge: M29 net hires

Definition: department-month hires minus exits. Positive values indicate net
hiring. It excludes transfers and inherits the M02/M03 five-person minimum.
The metric view combines `metrics.m02_hires` and `metrics.m03_exits`; the app
sums its reportable values over the selected department and date range.

Hand check: the raw `fact_headcount_monthly.csv` row for D01 / 2020-01 has
1 hire and 2 exits. Therefore M29 is $1 - 2 = -1$, matching
`metrics.m29_net_hiring` for that department-month. The automated comparison is
recorded in `metric_hand_checks.csv`.

Trace the number from dashboard KPI to M29, then to M02 hires and M03 exits,
and finally to the department-month row in the raw headcount file. In a star
schema, fact tables store measurements at a defined grain and dimension tables
provide descriptive context such as department, employee, location, or date.