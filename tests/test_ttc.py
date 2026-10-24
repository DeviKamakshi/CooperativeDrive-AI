"""Unit tests for app/core/ttc.py"""
import math
import pytest

from app.core.ttc import (
    mph_to_ms,
    heading_to_vector,
    compute_ttc_to_point,
    compute_vehicle_ttc,
    euclidean_distance,
)


def test_mph_to_ms():
    """60 mph ≈ 26.82 m/s."""
    result = mph_to_ms(60.0)
    assert abs(result - 26.82) < 0.01


def test_heading_to_vector_north():
    """Heading 0° (North) → (0, 1)."""
    vx, vy = heading_to_vector(0.0)
    assert abs(vx - 0.0) < 1e-9
    assert abs(vy - 1.0) < 1e-9


def test_heading_to_vector_east():
    """Heading 90° (East) → (1, 0)."""
    vx, vy = heading_to_vector(90.0)
    assert abs(vx - 1.0) < 1e-9
    assert abs(vy - 0.0) < 1e-9


def test_heading_to_vector_south():
    """Heading 180° (South) → (0, -1)."""
    vx, vy = heading_to_vector(180.0)
    assert abs(vx - 0.0) < 1e-9
    assert abs(vy - (-1.0)) < 1e-9


def test_ttc_to_point_approaching():
    """Vehicle at (0,0) heading North at 60 mph, point at (0, 100) → TTC ≈ 3.73 s."""
    speed_ms = mph_to_ms(60.0)
    expected = 100.0 / speed_ms  # ≈ 3.73
    ttc = compute_ttc_to_point(0.0, 0.0, 60.0, 0.0, 0.0, 100.0)
    assert ttc is not None
    assert abs(ttc - expected) < 0.01


def test_ttc_to_point_moving_away():
    """Vehicle at (0,0) heading South at 60 mph, point at (0, 100) → None."""
    ttc = compute_ttc_to_point(0.0, 0.0, 60.0, 180.0, 0.0, 100.0)
    assert ttc is None


def test_ttc_to_point_perpendicular():
    """Vehicle at (0,0) heading East, point at (0, 100) (due North) → None."""
    ttc = compute_ttc_to_point(0.0, 0.0, 60.0, 90.0, 0.0, 100.0)
    assert ttc is None


def test_vehicle_ttc_head_on():
    """Two vehicles approaching each other head-on → positive TTC."""
    # v1 at (0, 0) heading North; v2 at (0, 100) heading South
    ttc = compute_vehicle_ttc(
        0.0, 0.0, 30.0, 0.0,
        0.0, 100.0, 30.0, 180.0,
        conflict_radius_m=5.0,
    )
    assert ttc is not None
    assert ttc > 0.0


def test_vehicle_ttc_diverging():
    """Two vehicles moving away from each other → None."""
    # v1 at (0, 0) heading South; v2 at (0, 100) heading North (both moving away)
    ttc = compute_vehicle_ttc(
        0.0, 0.0, 30.0, 180.0,
        0.0, 100.0, 30.0, 0.0,
        conflict_radius_m=5.0,
    )
    assert ttc is None


def test_euclidean_distance():
    """distance((0,0), (3,4)) == 5.0."""
    assert euclidean_distance(0.0, 0.0, 3.0, 4.0) == pytest.approx(5.0)
