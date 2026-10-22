# Task 5: workforce dashboard

## Five CEO questions

1. How many people are in departments large enough to report safely?
2. Is reportable headcount growing or shrinking over the selected period?
3. Which departments make up the largest share of the workforce?
4. How does reportable headcount divide across city tiers?
5. What is the reported work-mode mix?

## Evidence

Run the app with `streamlit run app.py`. The dashboard reads only the official
`metrics.m01_headcount`, `metrics.m02_hires`, and `metrics.m03_exits` views,
plus metric-layer views for the department labels and suppressed workforce
breakdowns. No raw or warehouse table is queried by the app.

The headcount KPIs follow M01's minimum group size of five. Location-tier and
work-mode breakdowns apply the same threshold at their own category grain, so
small groups are intentionally omitted. Their category totals may therefore
be lower than reportable department headcount.

Screenshots: `task5-workforce-dashboard.png` (summary and trend) and
`task5-workforce-breakdowns.png` (department mix).