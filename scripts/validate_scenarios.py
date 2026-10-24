"""Quick end-to-end validation of all 8 priority scenarios.

Verifies that each scenario reaches its expected risk level.

Run from the cooperative-drive directory:
    python scripts/validate_scenarios.py
"""
from __future__ import annotations

import sys

# Ensure project root is on the path when run from the scripts/ directory
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import RiskLevel
from app.scenarios.registry import get_scenario

# Expected risk levels per scenario (tick counts to reach them)
EXPECTED: dict[str, tuple[RiskLevel, int]] = {
    "s01": (RiskLevel.HIGH, 2),    # after 2 ticks: vision hazard + CAR_A approaching
    "s02": (RiskLevel.HIGH, 3),    # after 3 ticks: TTC overlap detected
    "s03": (RiskLevel.HIGH, 6),    # after 6 ticks: simultaneous lane change
    "s04": (RiskLevel.HIGH, 10),   # within 10 ticks: blind intersection close approach
    "s05": (RiskLevel.HIGH, 6),    # after 6 ticks: sudden braking chain
    "s06": (RiskLevel.HIGH, 1),    # from tick 0: wrong-way vehicle detected
    "s07": (RiskLevel.HIGH, 4),    # after 4 ticks: 2-vehicle confirmation
    "s08": (RiskLevel.MEDIUM, 4),  # after 4 ticks: conflict discount applied
}

PASS = "✓"
FAIL = "✗"


def validate_scenario(scenario_id: str, expected_risk: RiskLevel, ticks: int) -> bool:
    """Run *ticks* ticks and check the final risk level."""
    scenario = get_scenario(scenario_id)
    if scenario is None:
        print(f"  {FAIL} {scenario_id}: NOT FOUND in registry")
        return False

    scenario.reset()
    scenario.setup()

    frame = None
    # For s04: accept HIGH at any tick within the window (it may arrive before ticks)
    seen_expected = False
    for _ in range(ticks):
        frame = scenario.tick()
        rr = frame.risk_result
        if rr and rr["risk"] == expected_risk.value:
            seen_expected = True
            if scenario_id == "s04":  # s04 needs to see HIGH at some point
                break

    if frame is None:
        print(f"  {FAIL} {scenario_id}: no frame produced")
        return False

    # For scenarios that must hold a risk level at the final tick
    if scenario_id == "s04":
        ok = seen_expected
    else:
        rr = frame.risk_result
        ok = rr is not None and rr["risk"] == expected_risk.value

    if ok:
        print(f"  {PASS} {scenario_id}: {expected_risk.value} (as expected)")
    else:
        actual = frame.risk_result["risk"] if frame.risk_result else "None"
        codes = frame.risk_result.get("reason_codes", []) if frame.risk_result else []
        print(
            f"  {FAIL} {scenario_id}: expected {expected_risk.value}, "
            f"got {actual} | reason_codes={codes}"
        )
    return ok


def main() -> int:
    print("=" * 60)
    print("CooperativeDrive — Scenario Validation")
    print("=" * 60)

    results: list[bool] = []
    for sid, (expected, ticks) in EXPECTED.items():
        results.append(validate_scenario(sid, expected, ticks))

    passed = sum(results)
    total = len(results)
    print()
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        print("\nFAILED — some scenarios did not reach expected risk level.")
        return 1

    print("\nALL SCENARIOS VALIDATED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
