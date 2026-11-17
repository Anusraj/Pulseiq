# Task 18: Self-service KPI explorer with privacy

## Live release

**Public dashboard:** https://pulseiq-v9ipnnyywrctkvvzmvynam.streamlit.app/

The new **KPI Explorer** page is available from the sidebar. Its controls are
shown in the page so they remain usable even when the navigation sidebar is
collapsed. It reads only the published aggregate DuckDB snapshot; it never queries raw employee,
payroll-detail, or salary-level tables.

## Allowed metrics and dimensions

The explorer uses the governed metric catalog and exposes these metrics:

| Metric IDs | Metrics | Safe dimensions |
|---|---|---|
| M01-M05, M29 | Headcount, hires, exits, attrition, net hires | Company, Department |
| M07, M09 | Gross pay and employer payroll cost | Company, Department |
| M13, M27 | Attendance rate and high-risk share | Company, Department |
| M16-M18 | Revenue, net profit, operating margin | Company |
| M22-M25 | Completion, on-time delivery, velocity, cycle time | Company, Department, Team |

Every result uses the metric catalog minimum group size, with an additional
five-record privacy floor. Groups below the threshold are filtered before
rendering and never appear in the table.

## Role views

The role selector uses the supplied `starter/demo_users.csv` identities as a
safe demonstration of role-based views:

| Demo user | Role | Allowed view |
|---|---|---|
| `admin.demo` | ADMIN | All governed aggregate metrics and drill levels |
| `hr.demo` | HR | People and payroll aggregates at company and department |
| `manager.demo` | MANAGER | Delivery metrics for the demonstration team only |
| `exec.demo` | EXECUTIVE | Company-level KPIs only |

This is a role-view demonstration, not authentication. Production identity
and authorization must be supplied by the hosting platform or SSO.

## Drill-down and break-it test

The explorer supports Company, Department, and Team drill levels where the
selected metric has a safe grain. Team drill-down is limited to delivery
metrics. A manager team with three people or fewer than five reportable tasks
returns a clear “no reportable group” message rather than a value.

Break-it cases tested:

1. Selected a manager role and attempted to choose payroll or company-only
   metrics: those metrics are absent from the allowed metric list.
2. Selected the manager team and a small-group delivery metric: the result is
   empty and the privacy message is shown.
3. Selected Team for a non-team metric: the explorer stops with a clear
   explanation instead of inventing a team value.
4. Selected an HR or manager role and attempted company/team drill levels:
   unavailable dimensions are not offered.

## Completion checklist

- [x] Small groups never appear.
- [x] Different demo roles see different data and drill levels.
- [x] Break-it privacy tests were run and unsafe paths were blocked.
- [x] Explorer deployed to the live Streamlit app.
- [x] Metric and dimension permissions are documented.
- [x] The manager-of-three decision is explicit: no attrition or delivery
  value is shown for a group below the privacy threshold.
