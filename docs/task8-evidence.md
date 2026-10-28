# Task 8: team productivity dashboard

## Page and governed metrics

The **Team productivity** page is available from Streamlit's multipage
navigation. It reads the governed M22-M25 views and the
`metrics.dashboard_team_sprint_productivity` supporting view. Choose a sprint
to compare teams, or choose a team to see its sprint trend. The latest sprint
is selected by default. The reportable view covers all 16 teams across 38
sprints (608 team/sprint rows).

- **Velocity (M24):** sum of story points for tasks whose current status is
  Done in the sprint. Cancelled tasks contribute no points.
- **Cycle time (M25):** mean calendar days from `started_date` to
  `completed_date` for Done tasks with both dates. Cancelled tasks are
  excluded.
- **On-time rate (M23):** Done tasks marked `completed_on_time = Y` divided by
  all Done tasks in the sprint. Cancelled tasks are excluded.
- **Completion rate (M22):** Done tasks divided by all non-cancelled tasks in
  the sprint.
- **Cancelled work:** excluded from the planned-task denominator and the
  governed delivery metrics, shown separately.
- **Blocked work:** remains in planned work and is highlighted by its current
  status.
- **Reopened work:** Done tasks remain in the delivery metrics if their
  current status is Done. A reopened task is separately counted when
  `reopened_count > 0`; reopen events sum that field. Blocked and reopened
  categories can overlap.

Team size, planning cadence, work types and sprint length are exposed as
comparison context. Velocity is not presented as a cross-team productivity
ranking. Team/sprint groups below the M22 five-task minimum are suppressed.

## Two-team hand verification

Both teams were independently recalculated from `data/raw/fact_task.csv` for
Sprint 38 (September 7-18, 2026; 10 working days), then compared with the
governed metric views. The arithmetic below uses only tasks for the specified
team and sprint.

| Team | Planned, excluding cancelled | Done | M22 completion | M23 on-time | M24 velocity | M25 cycle time | Blocked | Reopened tasks / events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Support Tooling (T12) | 110 | 87 | 87 / 110 = 79.09% | 78 / 87 = 89.66% | 332 points | 466 / 87 = 5.36 days | 5 | 4 / 5 |
| HR Systems (T13) | 41 | 36 | 36 / 41 = 87.80% | 32 / 36 = 88.89% | 119 points | 170 / 36 = 4.72 days | 0 | 6 / 6 |

The hand-calculated figures match the respective M22, M23, M24 and M25
metric-view values. Team context in the dimension is 58 active members for
Support Tooling and 19 for HR Systems; these counts and different task mixes
make raw point totals unsuitable for a fair productivity ranking.

## Three findings (default: Sprint 38)

1. **Support Tooling had the highest velocity:** 332 story points with 58
   active members; it also had 5 currently blocked tasks and 4 reopened tasks.
2. **HR Systems had the most reopened tasks:** 6 tasks (6 reopen events) among
   41 non-cancelled tasks, compared with 4 reopened tasks among Support
   Tooling's 110. HR Systems had 0 blocked tasks, 119 points and a 4.72-day
   average cycle time.
3. **Support Tooling had the most currently blocked work:** 5 tasks, alongside
   89.66% on-time delivery and a 5.36-day average cycle time.

These are signals for follow-up, not a single health score. For example,
Support Tooling's 332 points cannot by itself establish that it is healthier
than HR Systems: it has more active members, while HR Systems has more reopened
tasks per planned task (6/41 versus 4/110), no currently blocked tasks, and a
shorter observed cycle time. Differences in capacity and work mix need review
before drawing a team-level conclusion.

## Screenshot evidence

The page and all interactive controls were verified using Streamlit's
`AppTest`. A rendered screenshot is not included because this Windows
environment blocks the Streamlit executable through Application Control.
Capture the page as `docs/task8-team-productivity.png` from an
organization-approved Streamlit environment if a screenshot is required for
the accompanying report.

## Validation

- `python metrics.py` rebuilt all 29 official metric views. M22-M25 each
  contain 608 reportable team/sprint rows and passed their minimum-size checks;
  all six metric hand checks passed.
- Independent raw-data calculations for Support Tooling and HR Systems in
  Sprint 38 matched the governed M22-M25 values.
- `python -m py_compile pages/4_Team_Productivity.py` passed.
- Streamlit `AppTest` rendered the default all-team view and a team-filtered
  view without exceptions.
