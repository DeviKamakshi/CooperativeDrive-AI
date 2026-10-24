"""Time-to-Conflict (TTC) calculations.

Coordinate system: x increases East, y increases North.
Heading: 0° = North (+y), 90° = East (+x), 180° = South, 270° = West.
"""
from __future__ import annotations

import math


_MPH_TO_MS = 0.44704  # 1 mph in m/s


def mph_to_ms(speed_mph: float) -> float:
    """Convert miles per hour to metres per second."""
    return speed_mph * _MPH_TO_MS


def heading_to_vector(heading_degrees: float) -> tuple[float, float]:
    """Convert a compass heading (0=North, 90=East) to a unit (vx, vy) vector.

    Returns (vx, vy) where vx is the East component and vy is the North component.
    """
    rad = math.radians(heading_degrees)
    vx = math.sin(rad)   # East component
    vy = math.cos(rad)   # North component
    return (vx, vy)


def compute_ttc_to_point(
    vehicle_x: float,
    vehicle_y: float,
    vehicle_speed_mph: float,
    vehicle_heading_degrees: float,
    point_x: float,
    point_y: float,
) -> float | None:
    """Compute time in seconds for the vehicle to reach a stationary point.

    Considers only the closing component of velocity along the vehicle-to-point
    direction. Returns None if the vehicle is moving away from the point.
    """
    delta_x = point_x - vehicle_x
    delta_y = point_y - vehicle_y
    distance_m = math.hypot(delta_x, delta_y)

    if distance_m == 0.0:
        return 0.0

    # Bearing angle of the point from the vehicle (atan2 in standard math axes)
    bearing = math.atan2(delta_x, delta_y)  # atan2(East, North) gives compass angle

    speed_ms = mph_to_ms(vehicle_speed_mph)
    heading_rad = math.radians(vehicle_heading_degrees)

    # Closing speed = projection of velocity onto the vehicle→point direction
    closing_speed = speed_ms * math.cos(heading_rad - bearing)

    if closing_speed <= 1e-9:
        return None  # moving away or perpendicular

    return distance_m / closing_speed


def compute_vehicle_ttc(
    v1_x: float, v1_y: float, v1_speed_mph: float, v1_heading: float,
    v2_x: float, v2_y: float, v2_speed_mph: float, v2_heading: float,
    conflict_radius_m: float = 5.0,
) -> float | None:
    """Compute time in seconds until two vehicles come within conflict_radius_m.

    Uses constant-velocity linear projection and the quadratic formula on
    relative position + relative velocity. Returns None if they never come
    within conflict_radius_m.
    """
    v1x, v1y = heading_to_vector(v1_heading)
    v1_ms = mph_to_ms(v1_speed_mph)
    v2x, v2y = heading_to_vector(v2_heading)
    v2_ms = mph_to_ms(v2_speed_mph)

    # Relative position (v1 relative to v2)
    rx = v1_x - v2_x
    ry = v1_y - v2_y

    # Relative velocity (v1 relative to v2)
    dvx = v1x * v1_ms - v2x * v2_ms
    dvy = v1y * v1_ms - v2y * v2_ms

    # |r + dv*t|^2 = radius^2  →  a*t^2 + b*t + c = 0
    a = dvx * dvx + dvy * dvy
    b = 2.0 * (rx * dvx + ry * dvy)
    c = rx * rx + ry * ry - conflict_radius_m * conflict_radius_m

    if a == 0.0:
        # Vehicles have identical velocities; check if already within radius
        return 0.0 if c <= 0.0 else None

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return None  # never within radius

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    # Smallest non-negative root
    t_min = None
    for t in (t1, t2):
        if t >= 0.0:
            t_min = t if t_min is None else min(t_min, t)

    return t_min


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(x2 - x1, y2 - y1)
