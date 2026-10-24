"""Unit tests for IBM response parser and prompt builder in orchestrate.py."""
import pytest
from orchestrate import build_agent_prompt, parse_ibm_response


def test_parse_ibm_response_standard():
    sample = """
RISK: HIGH
HAZARD: Hidden pedestrian
WARNING: Pedestrian may enter road - wait before turning right.
REASON: CAR_A intends to turn into the affected area.
SEND TO: CAR_A
CONFIDENCE: HIGH
"""
    result = parse_ibm_response(sample, default_recipient="CAR_A")
    assert result["risk"] == "HIGH"
    assert result["hazard"] == "Hidden pedestrian"
    assert result["warning"] == "Pedestrian may enter road - wait before turning right."
    assert result["reason"] == "CAR_A intends to turn into the affected area."
    assert result["recipients"] == ["CAR_A"]
    assert result["confidence"] == "HIGH"


def test_parse_ibm_response_markdown_bold():
    sample = """
**RISK:** MEDIUM
**HAZARD:** Road debris in adjacent lane
**WARNING:** Caution - road debris reported in lane 3.
**REASON:** Debris present near intended path.
**SEND TO:** CAR_A
**CONFIDENCE:** HIGH
"""
    result = parse_ibm_response(sample)
    assert result["risk"] == "MEDIUM"
    assert "debris" in result["hazard"].lower()
    assert result["recipients"] == ["CAR_A"]
    assert result["confidence"] == "HIGH"


def test_parse_ibm_response_low_risk_none_recipient():
    sample = """
RISK: LOW
HAZARD: Clear roadway
WARNING: Safe to proceed.
REASON: No hazards reported.
SEND TO: NONE
CONFIDENCE: HIGH
"""
    result = parse_ibm_response(sample, default_recipient="CAR_A")
    assert result["risk"] == "LOW"
    assert result["recipients"] == []
    assert result["confidence"] == "HIGH"


def test_parse_ibm_response_empty():
    result = parse_ibm_response("")
    assert result["risk"] == "LOW"
    assert result["hazard"] == "Road clear"
    assert isinstance(result["recipients"], list)


def test_build_agent_prompt_structure():
    vehicle_context = {
        "vehicle_id": "CAR_A",
        "speed": "45 mph",
        "current_lane": "1",
        "target_lane": "2",
        "direction": "NORTH",
        "intended_maneuver": "CHANGE_RIGHT",
    }
    observation = "Debris scattered across lane 2."
    prompt = build_agent_prompt(vehicle_context, observation, source_vehicle="CAR_B")

    assert "CAR_A" in prompt
    assert "45 mph" in prompt
    assert "CHANGE_RIGHT" in prompt
    assert "Debris scattered" in prompt
    assert "CAR_B" in prompt
    assert "RISK: [HIGH | MEDIUM | LOW]" in prompt
