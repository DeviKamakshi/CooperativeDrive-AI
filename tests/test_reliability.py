"""Unit tests for app/core/reliability_tracker.py"""
import pytest

from app.core.reliability_tracker import ReliabilityTracker


@pytest.fixture()
def tracker():
    """Fresh ReliabilityTracker for each test."""
    return ReliabilityTracker()


def test_initial_score(tracker):
    """New vehicle starts at 0.80."""
    assert tracker.get_reliability("v1") == pytest.approx(0.80)


def test_confirmation_nudges_up(tracker):
    """Score after one confirmation is greater than 0.80."""
    score = tracker.record_confirmation("v1")
    assert score > 0.80


def test_conflict_nudges_down(tracker):
    """Score after one conflict is less than 0.80."""
    score = tracker.record_conflict("v1")
    assert score < 0.80


def test_max_clamp(tracker):
    """Many confirmations never push score above 1.0."""
    for _ in range(200):
        score = tracker.record_confirmation("v1")
    assert score <= 1.0


def test_min_clamp(tracker):
    """Many conflicts never push score below 0.2."""
    for _ in range(200):
        score = tracker.record_conflict("v1")
    assert score >= 0.2


def test_reset(tracker):
    """After modification, reset returns to 0.80."""
    tracker.record_confirmation("v1")
    assert tracker.get_reliability("v1") != pytest.approx(0.80)
    tracker.reset("v1")
    assert tracker.get_reliability("v1") == pytest.approx(0.80)


def test_all_scores(tracker):
    """all_scores returns a correct dict of current scores."""
    tracker.get_reliability("v1")
    tracker.get_reliability("v2")
    tracker.record_confirmation("v2")
    scores = tracker.all_scores()
    assert "v1" in scores
    assert "v2" in scores
    assert scores["v1"] == pytest.approx(0.80)
    assert scores["v2"] > 0.80
    # Returned dict is a copy — mutations must not affect tracker
    scores["v1"] = 0.0
    assert tracker.get_reliability("v1") == pytest.approx(0.80)
