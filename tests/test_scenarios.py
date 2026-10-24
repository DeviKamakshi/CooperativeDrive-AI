"""Integration tests for ST-07 scenario simulations (s03–s06).

Each test class:
- Calls scenario.reset() and scenario.setup() in its fixture to avoid cross-test pollution.
- Tests the scenario by calling .tick() directly (no HTTP layer).
"""
from __future__ import annotations

import pytest

from app.models import RiskLevel, ReasonCode
from app.scenarios.definitions.s03_simultaneous_lane_change import SimultaneousLaneChangeScenario
from app.scenarios.definitions.s04_blind_intersection import BlindIntersectionScenario
from app.scenarios.definitions.s05_sudden_braking import SuddenBrakingScenario
from app.scenarios.definitions.s06_wrong_way import WrongWayScenario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh(scenario_cls):
    """Return a reset+setup instance of the given scenario class."""
    s = scenario_cls()
    s.reset()
    s.setup()
    return s


def _tick_n(scenario, n: int):
    """Advance n ticks; return the last ScenarioFrame."""
    frame = None
    for _ in range(n):
        frame = scenario.tick()
    return frame


# ---------------------------------------------------------------------------
# Demo 3 — Simultaneous Lane Change
# ---------------------------------------------------------------------------


class TestS03SimultaneousLaneChange:
    def test_s03_setup(self):
        """After setup(), two vehicles should be registered in the store."""
        s = _fresh(SimultaneousLaneChangeScenario)
        # The store is populated on first tick, but vehicles are defined in setup
        # We advance one tick so the store has them
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles

    def test_s03_no_conflict_before_maneuver(self):
        """Ticks 1–5 (tick_index 0–4 at call time): both KEEP_LANE → risk LOW or MEDIUM."""
        s = _fresh(SimultaneousLaneChangeScenario)
        # Advance 5 ticks (tick_index goes 0→4, i.e., before the lane change at index 5)
        frame = None
        for _ in range(5):
            frame = s.tick()
        assert frame is not None
        risk_result = frame.risk_result
        assert risk_result is not None
        # Should be LOW or at most MEDIUM before simultaneous lane change
        assert risk_result["risk"] in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value)

    def test_s03_high_risk_on_simultaneous_lane_change(self):
        """After tick 6 (both vehicles change lane at tick_index 5), risk=HIGH with INTENT_CONFLICT."""
        s = _fresh(SimultaneousLaneChangeScenario)
        # Tick through index 5 (6th tick call triggers the lane change)
        frame = _tick_n(s, 6)
        assert frame is not None
        risk_result = frame.risk_result
        assert risk_result is not None
        assert risk_result["risk"] == RiskLevel.HIGH.value, (
            f"Expected HIGH, got {risk_result['risk']}. "
            f"reason_codes={risk_result.get('reason_codes')}"
        )
        assert ReasonCode.INTENT_CONFLICT.value in risk_result["reason_codes"], (
            f"INTENT_CONFLICT missing from {risk_result['reason_codes']}"
        )


# ---------------------------------------------------------------------------
# Demo 4 — Blind Intersection
# ---------------------------------------------------------------------------


class TestS04BlindIntersection:
    def test_s04_setup(self):
        """After setup(), two vehicles are present approaching the intersection."""
        s = _fresh(BlindIntersectionScenario)
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles

    def test_s04_high_risk_at_close_approach(self):
        """As both vehicles converge on the intersection their TTCs align → HIGH risk."""
        s = _fresh(BlindIntersectionScenario)
        # Run enough ticks for them to get close enough: ~6–8 ticks at 35–40 mph
        # CAR_A starts 80m south: 80m / (35 mph * 0.447 m/s/mph) ≈ 5.1 s
        # Run 10 ticks to be safe
        last_risk = None
        for _ in range(10):
            frame = s.tick()
            if frame.risk_result and frame.risk_result["risk"] == RiskLevel.HIGH.value:
                last_risk = frame.risk_result
                break

        assert last_risk is not None, (
            "Expected HIGH risk when both vehicles are simultaneously close "
            "to the intersection, but it never appeared in 10 ticks."
        )


# ---------------------------------------------------------------------------
# Demo 5 — Sudden Braking Chain
# ---------------------------------------------------------------------------


class TestS05SuddenBraking:
    def test_s05_setup(self):
        """After setup(), three vehicles exist in correct positions."""
        s = _fresh(SuddenBrakingScenario)
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles
        assert "CAR_C" in frame.vehicles
        # CAR_C should start furthest East
        assert frame.vehicles["CAR_C"]["position"]["x"] > frame.vehicles["CAR_B"]["position"]["x"]
        assert frame.vehicles["CAR_B"]["position"]["x"] > frame.vehicles["CAR_A"]["position"]["x"]

    def test_s05_low_risk_before_braking(self):
        """Ticks 1–5 (pre-braking): CAR_A risk should be LOW."""
        s = _fresh(SuddenBrakingScenario)
        frame = _tick_n(s, 5)
        assert frame is not None
        risk_result = frame.risk_result
        assert risk_result is not None
        assert risk_result["risk"] == RiskLevel.LOW.value, (
            f"Expected LOW before braking, got {risk_result['risk']}"
        )

    def test_s05_high_risk_after_braking(self):
        """After tick 6 (CAR_C brakes at index 5): CAR_A risk=HIGH with SUDDEN_BRAKING_AHEAD."""
        s = _fresh(SuddenBrakingScenario)
        frame = _tick_n(s, 6)
        assert frame is not None
        risk_result = frame.risk_result
        assert risk_result is not None
        assert risk_result["risk"] == RiskLevel.HIGH.value, (
            f"Expected HIGH after braking, got {risk_result['risk']}. "
            f"reason_codes={risk_result.get('reason_codes')}"
        )
        assert ReasonCode.SUDDEN_BRAKING_AHEAD.value in risk_result["reason_codes"], (
            f"SUDDEN_BRAKING_AHEAD missing from {risk_result['reason_codes']}"
        )


# ---------------------------------------------------------------------------
# Demo 6 — Wrong-Way Vehicle
# ---------------------------------------------------------------------------


class TestS06WrongWay:
    def test_s06_setup(self):
        """After setup(), wrong-way and two normal vehicles are present."""
        s = _fresh(WrongWayScenario)
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles
        assert "CAR_WRONG" in frame.vehicles

    def test_s06_high_risk_for_car_a(self):
        """CAR_A (ego) detects wrong-way vehicle → HIGH risk with WRONG_WAY_VEHICLE."""
        s = _fresh(WrongWayScenario)
        frame = s.tick()
        risk_result = frame.risk_result
        assert risk_result is not None
        assert risk_result["risk"] == RiskLevel.HIGH.value, (
            f"Expected HIGH risk for CAR_A, got {risk_result['risk']}. "
            f"reason_codes={risk_result.get('reason_codes')}"
        )
        assert ReasonCode.WRONG_WAY_VEHICLE.value in risk_result["reason_codes"], (
            f"WRONG_WAY_VEHICLE missing from {risk_result['reason_codes']}"
        )

    def test_s06_car_b_not_warned(self):
        """CAR_B (already past danger zone) should NOT be in intended_recipients of URGENT messages."""
        s = _fresh(WrongWayScenario)
        frame = s.tick()
        # Find HAZARD messages about WRONG_WAY_VEHICLE
        urgent_msgs = [
            m for m in frame.messages_this_tick
            if m.get("payload", {}).get("hazard_type") == "WRONG_WAY_VEHICLE"
        ]
        # There should be at least one such message
        assert urgent_msgs, "Expected at least one WRONG_WAY_VEHICLE hazard message"
        for msg in urgent_msgs:
            recipients = msg.get("intended_recipients", [])
            assert "CAR_B" not in recipients, (
                f"CAR_B incorrectly listed in recipients of wrong-way warning: {recipients}"
            )


# ---------------------------------------------------------------------------
# Demo 1 — Hidden Pedestrian
# ---------------------------------------------------------------------------


class TestS01HiddenPedestrian:
    def _scenario(self):
        from app.scenarios.definitions.s01_hidden_pedestrian import HiddenPedestrianScenario
        return _fresh(HiddenPedestrianScenario)

    def test_s01_setup(self):
        """After first tick, CAR_A and CAR_B are in the frame."""
        s = self._scenario()
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles

    def test_s01_vision_observation_at_tick_0(self):
        """After first tick, a HIDDEN_PEDESTRIAN hazard should be in the store."""
        s = self._scenario()
        s.tick()  # tick 0 triggers vision
        hazards = s.store.all_hazards()
        hidden_ped = [h for h in hazards if h.hazard_type.value == "HIDDEN_PEDESTRIAN"]
        assert hidden_ped, (
            f"Expected HIDDEN_PEDESTRIAN hazard after tick 0, got: "
            f"{[h.hazard_type.value for h in hazards]}"
        )

    def test_s01_high_risk_for_car_a(self):
        """After 2 ticks, CAR_A (TURN_RIGHT) risk should be HIGH."""
        s = self._scenario()
        frame = _tick_n(s, 2)
        assert frame is not None
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] == RiskLevel.HIGH.value, (
            f"Expected HIGH for CAR_A after 2 ticks, got {rr['risk']}. "
            f"reason_codes={rr.get('reason_codes')}"
        )

    def test_s01_watsonx_explanation_path(self):
        """Risk result has a risk level; explanation field is None (deterministic fallback ok)."""
        s = self._scenario()
        frame = _tick_n(s, 2)
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value, RiskLevel.HIGH.value)
        # watsonx_explanation may be None (deterministic fallback) — that is acceptable
        # The key assertion: explanation_source exists in the result
        assert "explanation_source" in rr


# ---------------------------------------------------------------------------
# Demo 2 — Highway Merge
# ---------------------------------------------------------------------------


class TestS02HighwayMerge:
    def _scenario(self):
        from app.scenarios.definitions.s02_highway_merge import HighwayMergeScenario
        return _fresh(HighwayMergeScenario)

    def test_s02_setup(self):
        """After first tick, both vehicles (CAR_HIGHWAY, CAR_MERGE) are present."""
        s = self._scenario()
        frame = s.tick()
        assert "CAR_HIGHWAY" in frame.vehicles
        assert "CAR_MERGE" in frame.vehicles

    def test_s02_high_risk_at_close_merge(self):
        """When TTC gap is tight (early ticks), ego risk should be HIGH."""
        s = self._scenario()
        high_seen = False
        for _ in range(8):
            frame = s.tick()
            rr = frame.risk_result
            if rr and rr["risk"] == RiskLevel.HIGH.value:
                high_seen = True
                break
        assert high_seen, (
            "Expected HIGH risk for CAR_HIGHWAY when merge TTC overlap is tight "
            "(within first 8 ticks)"
        )

    def test_s02_risk_reduces_with_gap(self):
        """After CAR_HIGHWAY decelerates (post tick 8), risk should drop to MEDIUM or LOW."""
        s = self._scenario()
        for _ in range(12):
            frame = s.tick()
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] in (RiskLevel.MEDIUM.value, RiskLevel.LOW.value), (
            f"Expected risk to drop after deceleration, got {rr['risk']}. "
            f"reason_codes={rr.get('reason_codes')}"
        )


# ---------------------------------------------------------------------------
# Demo 7 — Road Debris
# ---------------------------------------------------------------------------


class TestS07RoadDebris:
    def _scenario(self):
        from app.scenarios.definitions.s07_road_debris import RoadDebrisScenario
        return _fresh(RoadDebrisScenario)

    def test_s07_unconfirmed_on_first_report(self):
        """At tick 0, debris hazard should be UNCONFIRMED, and CAR_A risk MEDIUM or HIGH."""
        s = self._scenario()
        frame = s.tick()
        debris = [h for h in s.store.all_hazards() if h.hazard_type.value == "ROAD_DEBRIS"]
        assert debris, "Expected ROAD_DEBRIS hazard after tick 0"
        assert debris[0].status.value == "UNCONFIRMED", (
            f"Expected UNCONFIRMED status, got {debris[0].status.value}"
        )
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] in (RiskLevel.MEDIUM.value, RiskLevel.HIGH.value), (
            f"Expected MEDIUM or HIGH after unconfirmed report, got {rr['risk']}"
        )

    def test_s07_confirmed_after_two_vehicles(self):
        """After tick 3 (CAR_C confirms), debris status should be CONFIRMED."""
        s = self._scenario()
        _tick_n(s, 4)   # tick 0 injects, tick 3 confirms → need 4 ticks total
        debris = [h for h in s.store.all_hazards() if h.hazard_type.value == "ROAD_DEBRIS"]
        assert debris, "Expected ROAD_DEBRIS hazard to still exist"
        assert debris[0].status.value == "CONFIRMED", (
            f"Expected CONFIRMED after CAR_C confirmation, got {debris[0].status.value}"
        )

    def test_s07_high_risk_after_confirmation(self):
        """After tick 3+, CAR_A risk should be HIGH."""
        s = self._scenario()
        frame = _tick_n(s, 4)
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] == RiskLevel.HIGH.value, (
            f"Expected HIGH after debris confirmation, got {rr['risk']}. "
            f"reason_codes={rr.get('reason_codes')}"
        )


# ---------------------------------------------------------------------------
# Demo 8 — Conflicting Reports
# ---------------------------------------------------------------------------


class TestS08ConflictingReports:
    def _scenario(self):
        from app.scenarios.definitions.s08_conflicting_reports import ConflictingReportsScenario
        return _fresh(ConflictingReportsScenario)

    def test_s08_setup(self):
        """After first tick, all three vehicles are present."""
        s = self._scenario()
        frame = s.tick()
        assert "CAR_A" in frame.vehicles
        assert "CAR_B" in frame.vehicles
        assert "CAR_C" in frame.vehicles

    def test_s08_conflicted_after_contradiction(self):
        """After tick 3 (CAR_C conflicts), road blockage status should be CONFLICTED."""
        s = self._scenario()
        _tick_n(s, 4)  # tick 0 reports, tick 3 conflicts → need 4 ticks
        # Hazard type is ROAD_BLOCKAGE in s08 (higher severity to reach MEDIUM after discount)
        hazard = [h for h in s.store.all_hazards()
                  if h.hazard_type.value in ("ROAD_DEBRIS", "ROAD_BLOCKAGE")]
        assert hazard, "Expected a road hazard to still exist in the store"
        assert hazard[0].status.value == "CONFLICTED", (
            f"Expected CONFLICTED after CAR_C contradiction, got {hazard[0].status.value}"
        )

    def test_s08_medium_risk_with_conflicting_evidence(self):
        """After tick 3+, risk should be MEDIUM and CONFLICTING_EVIDENCE should be present."""
        s = self._scenario()
        frame = _tick_n(s, 4)
        rr = frame.risk_result
        assert rr is not None
        assert rr["risk"] == RiskLevel.MEDIUM.value, (
            f"Expected MEDIUM after conflict discount, got {rr['risk']}. "
            f"reason_codes={rr.get('reason_codes')}"
        )
        assert ReasonCode.CONFLICTING_EVIDENCE.value in rr["reason_codes"], (
            f"CONFLICTING_EVIDENCE missing from {rr['reason_codes']}"
        )
