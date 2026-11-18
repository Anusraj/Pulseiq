# Final handover

## Board story

PulseIQ turns raw operational feeds into a governed workforce product. The
current story is growth with control: headcount is scaling, cash collection
needs ownership, team delivery varies, and one payroll reconciliation issue
must be closed before cost action.

## Five findings and decisions

1. **People:** headcount grew from 392 to 440 in the latest 12-month view.
   Recommendation: plan capacity and manager span before growth creates an
   execution bottleneck.
2. **Retention:** September monthly attrition was 0.69%; the rolling view is
   the safer board measure because monthly values are noisy. Recommendation:
   investigate persistent department movement, not a single spike.
3. **Cost:** September employer payroll cost was INR 55.0M, but June has an
   INR 18,450 payroll-to-ledger mismatch. Recommendation: do not approve a
   cost intervention until Finance closes DQ-C01.
4. **Cash:** DSO was 48 days and the largest overdue client balance was about
   INR 6.1M. Recommendation: assign an owner and review collections weekly.
5. **Teams:** latest sprint completion ranged from 75.9% to 92.9% across
   reportable teams. Recommendation: share planning practices without ranking
   teams on velocity alone.

## Judgement call

**I would not recommend a payroll reduction or cost intervention yet because
the live payroll-versus-ledger reconciliation has a critical June mismatch of
INR 18,450; the cost number is not strong enough for that decision.**

## Handover owners

| Area | Next owner | Next action |
| --- | --- | --- |
| DQ-C01 | Finance + Data Engineering | Explain and reconcile June 2026 |
| Cash | Finance / Collections | Own the INR 6.1M overdue account |
| Retention | HR Analytics | Review rolling attrition by department |
| Delivery | Engineering Ops | Pair the lowest completion team with a strong team |
| Product | Analytics Engineering | Keep metric catalog and API freshness current |

## Operational entry points

- Dashboard: `streamlit run app.py`
- KPI Explorer: `streamlit run pages\12_KPI_Explorer.py`
- Metrics API: `uvicorn metrics_api:app --app-dir phase4\task-19`
- Board pack rebuild: `python phase4\TASK20\build_task20.py`
