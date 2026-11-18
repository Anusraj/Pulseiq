# Release check evidence

The live check output is [release_checks.json](release_checks.json). It was
generated from the repository's current `pulseiq.duckdb` and existing live
check outputs.

## Results

- Warehouse reconciliation: **PASS** — 14 tables, zero non-pass rows.
- Metric layer: **PASS** — 29 catalog metrics, 29 validated views, zero
  below-threshold groups in the validation report.
- Data quality: **CONDITIONAL** — DQ-C01 has one critical failure:
  June 2026 payroll `54,664,233.35` versus ledger `54,682,683.35`, a
  difference of approximately INR 18,450.
- Warnings remain visible for attendance after exit, unpaid leave deduction,
  invoice/expense arithmetic, task/leave dates, AI freshness, and minimum
  reference group size.

This is why the release is not described as an unconditional clean pass.
