# PulseIQ v1.0.0 release notes

Release date: 2026-11-18

## Included

- Validated ETL and data-quality gate for HR, payroll, ledger, invoice, task,
  attendance, leave, forecast, and AI feeds.
- Dimensional DuckDB warehouse with employee history, facts, dimensions,
  reconciliation, orphan, and SCD checks.
- Governed metric layer with 29 metric views, catalog definitions, hand checks,
  and minimum-group suppression.
- Streamlit workforce dashboard with period and department filters.
- Privacy-safe KPI Explorer with role-aware metrics and dimensions.
- Read-only FastAPI service exposing five metrics with definitions, lineage,
  sources, and freshness.
- Nine-slide board deck, evidence snapshot, final handover, and demo script.

## Not included

- Production authentication or SSO authorization for the demo roles/API.
- An always-on API service managed by this repository; deployment remains a
  separate service from the Streamlit host.
- Automated browser regression coverage across all dashboard pages.
- A recorded video file. The live demo URL and a timed presenter runbook are
  supplied in `demo_script.md`.

## Known limits

- The public release is aggregate-only, but groups below the privacy threshold
  are suppressed at each metric grain.
- DQ-C01 currently fails for June 2026: payroll and ledger differ by
  approximately INR 18,450. Cost decisions are explicitly gated on resolving
  this issue.
- Several warning checks remain visible in the DQ output, including stale AI
  records, planted date issues, and below-threshold reference groups.
- Streamlit Community Cloud may sleep between visits.

## Release decision

**Conditional release.** The product is suitable for governed monitoring of
people, cash, and delivery. It is not approved for a payroll-cost intervention
until the June 2026 reconciliation is explained and rerun successfully.

The v1.0.0 tag is created locally after the Task 20 base commit. It is not
pushed by request.
