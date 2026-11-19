"""Turn Task 20 release checks into an explicit decision for cost consumers."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "release_checks.json"
OUTPUT = ROOT / "decision_guard_result.json"


def decide() -> dict[str, object]:
    checks = json.loads(CHECKS.read_text(encoding="utf-8"))
    critical_failures = checks["data_quality"]["critical_failures"]
    if critical_failures:
        decision = "HOLD_COST_ACTION"
        reason = (
            "A critical live-data quality failure remains. Resolve DQ-C01 "
            "before using payroll or cost metrics for intervention decisions."
        )
    else:
        decision = "APPROVE_MONITORING"
        reason = "No critical live-data quality failures remain."
    result = {
        "decision": decision,
        "reason": reason,
        "critical_failures": critical_failures,
        "source": "release_checks.json",
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(decide(), indent=2))
