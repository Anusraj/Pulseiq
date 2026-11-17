# Task 17: Production release

PulseIQ is deployed as a public Streamlit Community Cloud app from the
`Anusraj/Pulseiq` GitHub repository. The app reads
`data/pulseiq_public.duckdb`, a 17.6 MB snapshot containing only governed
aggregate metric outputs and release metadata. Raw feeds, warehouse tables,
employee-level tables, and `payroll_eligible` are not published.

## Hosting decision

| Platform | Free limits / data size | Sleeping behaviour | Price |
|---|---|---|---|
| Streamlit Community Cloud | Public apps; repository files must remain within the platform's practical resource limits; this snapshot is 17.6 MB and below the 200 MB release budget | Apps can sleep after inactivity and cold-start on the next visit | Free |
| Render | Free web services have limited monthly hours and ephemeral local storage | Spins down after inactivity on the free tier | Free; paid services from a small monthly fee |
| Hugging Face Spaces | Public CPU Spaces have limited hardware/storage and may restart | Spaces can pause when unused | Free; paid hardware available |

Streamlit Community Cloud is the first choice because the product is already a
Streamlit app, deployment is directly connected to GitHub, and the published
aggregate file is comfortably below the 200 MB budget. Sleeping is acceptable
for this learning release; a paid always-on plan would be the normal business
choice if a cold start harmed operational users.

## Data, secrets, and refresh

- The public file is rebuilt with `python publish_public_data.py`.
- `.github/workflows/monthly-report.yml` runs at **06:00 UTC on the first day
  of every month**, rebuilds ETL, warehouse, and metric outputs, and commits
  the refreshed aggregate file when it changes.
- The dashboard displays the release metadata cut-off (`September 1, 2026`
  for the current snapshot).
- No secrets are required by the app. If a hosted database is added later,
  credentials belong in Streamlit Cloud Secrets, not Git or this file.

## Stranger test and checklist

- [ ] Live link opens on a phone and for a stranger: paste the deployed
  Streamlit URL here after the Cloud deploy is created.
- [x] Data cut-off is visible below the reporting-period filter.
- [x] No secrets are in the repository; the app uses only committed aggregate
  data.
- [x] Hosting choice and reason are documented above.
- [x] Landing page, sidebar navigation, department/date filters, and
  period-end headcount KPI are available. A stranger can open **Workforce**
  and read the first KPI without setup.
- [x] The published database is 17.6 MB, well below the 200 MB limit.

## Evidence

- Current release candidate report: [Task 16 evidence](../task-16/task16-evidence.md).
- Public data snapshot: `data/pulseiq_public.duckdb`.
- Phone screenshot: capture the deployed URL after the first Streamlit Cloud
  deployment and attach it to this report.
