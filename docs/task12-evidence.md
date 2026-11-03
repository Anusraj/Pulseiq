# Task 12: invoices, receivables and cash flow

## Page and rules

The page is `pages/8_Receivables_Cash.py`. It reads the governed views:

- `metrics.dashboard_receivables_ageing`
- `metrics.dashboard_receivables_summary`
- `metrics.dashboard_overdue_clients`
- `metrics.dashboard_client_days_to_pay`
- `metrics.dashboard_cash_flow_monthly`

Only `SENT`, `OVERDUE` and `PARTIALLY_PAID` invoices are open. `PAID`, `DRAFT`
and `CANCELLED` invoices are excluded. Ageing is measured in days past due as
of the latest invoice date. Not-yet-due invoices are assigned to `0-30 days`.

Cash in is invoice payments by payment date. Cash out is paid expense bills,
using total bill value including GST, by paid date.

## Receivables bucket total check

As of 30 September 2026:

| Ageing bucket | Open invoices | Receivables (INR) |
|---|---:|---:|
| 0-30 days | 59 | 134,417,038.00 |
| 31-60 days | 0 | 0.00 |
| 61-90 days | 1 | 1,940,982.00 |
| 90+ days | 2 | 3,036,258.00 |
| **Total buckets** | **62** | **139,394,278.00** |

The independent total open receivable is ₹139,394,278.00, so the difference
between the bucket sum and total is ₹0.00.

## Collections findings

1. **Siruvani Agro Tech** has ₹6,097,296 overdue and the oldest balance is
   548 days past due. It is also a risky client with average historical
   payment of 105.36 days against 45-day terms.
2. **Marina Media Works** has the largest overdue balance at ₹7,110,208,
   despite not appearing among the slowest historical payers. Finance should
   review the two open invoices for dispute or recent payment interruption.
3. **Triveni Steel Industries** is the slowest historical payer: 121.25 days
   average against 60-day terms, or 61.25 days over terms. A large client
   paying at 75 days is a risk when terms are 30 or 45 days because it creates
   a predictable funding gap; Finance should confirm whether the delay is
   contractually approved, whether credit limits reflect it, and whether
   overdue balances or disputes are increasing.

## Validation and evidence

- `python metrics.py` rebuilt the metric layer successfully.
- Bucket sum check: ₹139,394,278.00 − ₹139,394,278.00 = ₹0.00.
- Four ageing buckets are always returned, including zero-value buckets.
- The page states the exact open statuses on the page.
- `python -m py_compile pages/8_Receivables_Cash.py` passed.
- Streamlit AppTest rendered the page with no application exceptions.
- Capture the page in an approved Streamlit environment for screenshot evidence.
