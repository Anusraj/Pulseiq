# Final Challenge: decision guard for cost recommendations

## Independent improvement

I built a small release decision guard in `decision_guard.py`. It converts the
live release-check output into an explicit decision: `APPROVE_MONITORING` or
`HOLD_COST_ACTION`. This prevents a board pack or downstream consumer from
mistaking a conditional data-quality result for a clean cost signal.

## Why this design

The existing product exposes governed metrics, but a consumer still needs to
interpret DQ status. A typed decision with a reason makes the critical
reconciliation caveat executable and reusable without changing any metric
formula or hiding the failure.

## Branch and validation

- Local branch: `task20-final-challenge`
- Input: `release_checks.json`
- Output: `decision_guard_result.json`
- Decision on current data: `HOLD_COST_ACTION`

The branch is local only and was not pushed.
