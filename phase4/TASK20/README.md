# Task 20: Board pack and final handover

Task 20 packages the completed PulseIQ product for a board audience. The
deliverable is a nine-slide board deck, a release decision, live-data checks,
release notes, and a five-minute demo script.

## Deliverables

| File | Purpose |
| --- | --- |
| `board_deck.pdf` | Printable nine-slide board presentation |
| `board_deck.html` | Browser version of the same deck |
| `board_deck.md` | Slide-by-slide story, evidence, and recommendation |
| `board_data.json` | Snapshot values used to build the deck |
| `release_checks.json` | Reconciliation, metric-layer, and DQ results |
| `RELEASE_NOTES.md` | v1.0.0 scope, limits, and release decision |
| `final_handover.md` | Executive handover and decision log |
| `final_challenge.md` | Independent improvement and local branch notes |

## Rebuild

From the repository root:

```powershell
.\.venv\Scripts\python.exe phase4\TASK20\release_checks.py
.\.venv\Scripts\python.exe phase4\TASK20\build_task20.py
```

The builder reads the current read-only DuckDB snapshot and writes all
presentation outputs into this folder. It does not rewrite warehouse tables.

## Release status

The release is **CONDITIONAL_PASS**:

- Warehouse reconciliation: PASS, 14 fact tables with zero row differences.
- Metric layer: PASS, 29 catalog metrics and 29 validated views.
- DQ gate: CONDITIONAL because DQ-C01 reports a June 2026 payroll-versus-ledger
  difference of INR 18,450.

The board recommendation is to use people, cash, and team monitoring now, but
not approve a payroll-cost intervention until Finance closes DQ-C01.

## Checklist

- [x] Deck tells one clear story.
- [x] Reconciliations were re-checked on the live DuckDB snapshot.
- [x] DQ checks were re-checked and the critical failure is explicitly noted.
- [x] Release notes written for v1.0.0.
- [x] Demo runbook and tested live product link supplied.
- [x] Final challenge improvement implemented on a local branch.
