# Task 11: profit and loss and expense analytics

## Page and governed views

The P&L page is `pages/7_Profit_Loss.py`. It reads only the Task 11 metric
views:

- `metrics.dashboard_pnl_monthly` — monthly revenue, expense, profit and margin
  from ledger detail accounts.
- `metrics.dashboard_expense_category_monthly` — approved bill spend by
  expense category, excluding GST.
- `metrics.dashboard_expense_vendor_monthly` — approved bill spend by vendor,
  excluding GST.
- `metrics.dashboard_pnl_tieout` — P&L values compared with the README
  reconciliation headline.

`dim_account.is_group = 'N'` is required for every P&L account. The group
headings `4000 Income` and `5000 Expenses` are never included, so a heading
and its children cannot be counted together. Revenue includes detail income
account `4900 Other Income (Interest)` because that is included in the README
headline revenue.

## Tie-out table

The warehouse P&L agrees with the README headline for 17 of 18 months. The
remaining difference is the known seeded DQ-04 issue, not a dashboard
adjustment:

| Month | Revenue difference (INR) | Expense difference (INR) | Profit difference (INR) | Status |
|---|---:|---:|---:|---|
| Apr 2025 | 0.00 | 0.00 | 0.00 | Tie |
| May 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Jun 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Jul 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Aug 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Sep 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Oct 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Nov 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Dec 2025 | 0.00 | 0.00 | 0.00 | Tie |
| Jan 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Feb 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Mar 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Apr 2026 | 0.00 | 0.00 | 0.00 | Tie |
| May 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Jun 2026 | 0.00 | 18,450.00 | 18,450.00 | Investigate DQ-04 |
| Jul 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Aug 2026 | 0.00 | 0.00 | 0.00 | Tie |
| Sep 2026 | 0.00 | 0.00 | 0.00 | Tie |

DQ-04 identifies journal `JE-002094` and ledger lines `JL-005614` and
`JL-005643`. The journal balances, but the available evidence does not prove
which line should be corrected, so the page leaves the source unchanged and
flags June rather than silently forcing a tie.

## Independent check of the displayed month

The screenshot's selected month is September 2026. Recomputing directly from
the original `raw.fact_ledger` and `raw.dim_account` tables gives the same
values as both the README answer key and the dashboard view:

| Measure | Raw ledger | README headline | Dashboard | Difference |
|---|---:|---:|---:|---:|
| Revenue | ₹80,601,695.00 | ₹80,601,695.00 | ₹80,601,695.00 | ₹0.00 |
| Expenses | ₹65,615,715.87 | ₹65,615,715.87 | ₹65,615,715.87 | ₹0.00 |
| Net profit | ₹14,985,979.13 | ₹14,985,979.13 | ₹14,985,979.13 | ₹0.00 |

The arithmetic also agrees: `₹80,601,695.00 - ₹65,615,715.87 =
₹14,985,979.13`. No September ledger postings use the group accounts.

## Three findings

1. **Non-payroll costs may be rising faster than revenue.** Compare the monthly
   ledger expense trend with the category view; the largest month-on-month
   category increases identify the cost driver.
2. **Payroll mix or headcount growth may be absorbing revenue.** Compare the
   governed payroll-cost view with revenue and payroll-as-a-percent-of-revenue;
   headcount and cost-per-head distinguish hiring growth from rate or mix changes.
3. **A concentrated vendor spike may be leaking margin.** The top-10 chart ranks
   approved bill spend ex-GST; contract terms, purchase volumes and ledger
   postings prove whether a spike is recurring, one-off, or misclassified.

## Validation and evidence

- `python metrics.py` rebuilt all 29 existing official views and the four Task
  11 dashboard views.
- A direct warehouse check found zero ledger lines posted to group accounts.
- The tie-out view returned 18 months: 17 exact ties and the documented June
  DQ-04 exception.
- `python -m py_compile pages/7_Profit_Loss.py` passed.
- The page includes the monthly trend, selected-month P&L table, category
  chart, top-10 vendor chart, full tie-out table and the three findings.
- Capture the page in an approved Streamlit environment as the screenshot
  evidence; this Windows environment previously blocked the Streamlit
  executable through Application Control (see `docs/task10-evidence.md`).
- On affected Windows machines, run `python -m streamlit run app.py` instead of
  the blocked `streamlit run app.py` launcher.
