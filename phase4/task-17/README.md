# Task 17: Production release

## Live dashboard

**Public link:** https://pulseiq-v9ipnnyywrctkvvzmvynam.streamlit.app/

The app is deployed from `Anusraj/Pulseiq`, branch `main`, entry point
`app.py`, using Streamlit Community Cloud. It has a landing page, navigation,
department/date filters, a visible data cut-off, and the Workforce page's
period-end headcount KPI.

## Hosting choice

| Platform | Free limits / data size | Sleeping behaviour | Price |
|---|---|---|---|
| Streamlit Community Cloud | Public GitHub apps; this 17.6 MB snapshot is below the 200 MB release budget | May sleep after inactivity and cold-start on the next visit | Free |
| Render | Free web services have limited monthly hours and ephemeral local storage | Spins down after inactivity on free tier | Free; paid from a small monthly fee |
| Hugging Face Spaces | Public CPU Spaces have limited hardware/storage | May pause when unused | Free; paid hardware available |

Streamlit Community Cloud was chosen because the dashboard is already a
Streamlit app and deploys directly from GitHub. Sleeping is acceptable for
this learning release; a paid always-on plan would be normal if a cold start
hurt operational users.

## Published data and refresh

`data/pulseiq_public.duckdb` is 17.6 MB and contains only materialized,
governed metric aggregates and release metadata. Raw feeds, warehouse tables,
employee-level tables, and `payroll_eligible` are excluded. The current
cut-off is **1 September 2026**, shown on the Workforce landing page.

`.github/workflows/monthly-report.yml` runs at **06:00 UTC on the first day of
each month**, rebuilds ETL, warehouse, metric views, the report, and the
public snapshot, then commits the snapshot if it changed.

No secrets are required by the app. Future database credentials belong in
Streamlit Cloud Secrets, never in the repository.

## Completion checklist

- [x] Live link opens in a browser and the app navigation loads.
- [x] Data cut-off date is shown.
- [x] No secrets are in the repository.
- [x] Hosting choice and reason are documented.
- [x] Published data is below 200 MB.
- [x] Landing page, navigation, filters, and headcount KPI are available.
- [x] A stranger can open **Workforce** and read period-end headcount without
  setup.

## Phone evidence

Open the public link on a phone and capture the Workforce landing page with
the sidebar filters collapsed. The responsive CSS is included in
`dashboard.py`; the phone screenshot is the remaining manual evidence item.
