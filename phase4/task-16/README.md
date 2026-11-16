# Task 16 — Automated report builder and release candidate

This folder contains the complete Task 16 bundle:

- `build_report.py` — one-command stamped PDF generator.
- `requirements.txt` — pinned report/runtime dependencies.
- `tests/` — clean-machine and new-department regression test.
- `reports/` — sample monthly report.
- `task16-evidence.md` — completion evidence and release notes.
- The scheduled workflow is kept at
  `../../.github/workflows/monthly-report.yml` because GitHub only discovers
  scheduled workflows from `.github/workflows`.

From the repository root:

```powershell
python -m pip install -r phase4\task-16\requirements.txt
python phase4\task-16\build_report.py --month 2026-09
python -m unittest discover -s phase4\task-16\tests -p "test_*.py" -v
```
