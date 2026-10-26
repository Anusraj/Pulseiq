# Task 6: attendance and leave trends

## Page and filters

The Streamlit page is available as **Attendance** in the app navigation. It
shows monthly attendance rate, late arrivals, overtime hours, approved leave
days by type, and a department-by-month attendance heatmap. Department and
date-range filters apply to each chart and KPI.

The page reads governed views from `metrics.m13_attendance_rate` and
`metrics.m14_late_arrival_rate`, plus supporting views in `metric_views.sql`:

- `metrics.dashboard_attendance_overtime` aggregates attendance-fact overtime
  hours by department/month.
- `metrics.dashboard_leave_days_by_type` aggregates approved leave days by
  department, request-start month, and type.
- `metrics.dashboard_attendance_calendar` marks each month's holidays and
  holidays on Monday or Friday (adjacent to a weekend).

Every reportable group has at least five distinct employees. The M13 rate
uses `(present days + 0.5 × unpaid half-days) / scheduled days`; scheduled
days are the working-day denominator. The all-department monthly rate is
recalculated from summed M13 numerators and denominators, not by averaging
department percentages. Leave requests are assigned to the month in which
they start; only approved requests are included. Calendar annotations explain
context but do not imply that holidays cause a rate change.

## Three unusual months and numeric insights

1. **October 2025 — attendance dip and holiday cluster.** The weighted
   attendance rate was **93.87%**, down **1.61 percentage points** from
   September's 95.48%. The calendar records **three holidays** (October 2, 20,
   and 21), including a Monday holiday adjacent to the weekend. Because
   attendance is divided by scheduled working days, holidays are not in its
   denominator. The calendar makes this a reasonable timing hypothesis, not
   proof of a cause; investigate approved leave and department-level changes
   before attributing the dip to the holidays.
2. **December 2025 — overtime spike.** Overtime reached **787.0 hours**, about
   **44.4% above** the 18-month monthly average of approximately 545.2 hours.
   Attendance was 93.71%, and Christmas (December 25) is marked in the
   calendar. A year-end workload surge is plausible, but this dataset alone
   cannot establish workload as the cause; compare team schedules and leave
   before drawing that conclusion.
3. **May 2026 — lowest attendance and localized department change.** The
   company-wide rate was the period low at **92.87%**, down **0.47 percentage
   points** from April's 93.34%. Operations & IT (D10) fell to **83.61%**, a
   **10.83-point** decline from April, among **9
   employees**. May 1 is marked as a Friday holiday adjacent to the weekend;
   it is not counted as a scheduled workday. Start with D10's change rather
   than Engineering's size: the largest movement is the stronger diagnostic
   signal, while the small-but-reportable group size warrants checking the
   underlying pattern before treating it as representative.

## Denominator and privacy checks

- M13's denominator is `SUM(scheduled_days)`, not calendar days or headcount.
- The all-department rate is `SUM(numerator) / SUM(denominator)` for the
  selected reportable department-month rows.
- Attendance, lateness, overtime, and leave supporting views suppress
  department-month groups below the M13 five-person minimum. Leave groups are
  additionally separated by type before suppression.
- Holidays and Monday/Friday holiday dates are visible in the page's calendar
  table and in attendance-trend hover details.

## Evidence

Run `streamlit run app.py` and select **Attendance** from the app navigation.
The page's charts, KPI cards, heatmap, leave breakdown, and holiday table are
the screenshot evidence for this task. Metric views can be rebuilt and
validated with `python metrics.py`.
