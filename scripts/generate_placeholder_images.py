"""Generate placeholder road-scene images for CooperativeDrive scenarios.

These synthetic images stand in for real road footage until actual camera
frames are available. Each image includes scene geometry, labels, and a
prominent PLACEHOLDER watermark.

Run from the cooperative-drive directory:
    python scripts/generate_placeholder_images.py
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit(
        "Pillow is required: pip install Pillow"
    )

# ---------------------------------------------------------------------------
# Root of the static-assets tree (relative to this script's parent directory)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent / "app" / "static" / "assets" / "images"

_W, _H = 640, 480
_ROAD_GREY = (100, 100, 100)
_SKY_BLUE = (135, 180, 220)
_LANE_WHITE = (240, 240, 240)
_TRUCK_DARK = (50, 55, 60)
_DEBRIS_COLOR = (80, 70, 50)
_CAR_YELLOW = (220, 200, 50)
_TEXT_WHITE = (255, 255, 255)
_WARN_RED = (220, 50, 50)
_WATERMARK = (200, 50, 50)


def _base_road(draw: ImageDraw.ImageDraw) -> None:
    """Draw a simple two-lane road with sky and lane markings."""
    horizon = _H // 2
    # Sky
    draw.rectangle([(0, 0), (_W, horizon)], fill=_SKY_BLUE)
    # Road surface
    draw.rectangle([(0, horizon), (_W, _H)], fill=_ROAD_GREY)
    # Lane markings — dashed centre line
    y_centre = horizon + (_H - horizon) // 2
    for x in range(0, _W, 60):
        draw.rectangle([(x, y_centre - 3), (x + 30, y_centre + 3)], fill=_LANE_WHITE)
    # Road edges
    draw.rectangle([(0, horizon), (8, _H)], fill=_LANE_WHITE)
    draw.rectangle([(_W - 8, horizon), (_W, _H)], fill=_LANE_WHITE)


def _watermark(draw: ImageDraw.ImageDraw) -> None:
    """Overlay prominent placeholder watermark."""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        font = ImageFont.load_default()
        small = font

    text = "PLACEHOLDER — Synthetic Training Image"
    draw.text((10, _H - 28), text, fill=_WATERMARK, font=small)


def _label(draw: ImageDraw.ImageDraw, description: str, scenario_id: str) -> None:
    """Draw scenario ID badge and description text."""
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm = font_big

    # Badge
    draw.rectangle([(8, 8), (90, 32)], fill=(30, 30, 30))
    draw.text((12, 11), scenario_id.upper(), fill=(255, 200, 0), font=font_big)

    # Wrap description text across two lines (simple 60-char split)
    words = description.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > 60:
            lines.append(current)
            current = w
        else:
            current = (current + " " + w).strip()
    if current:
        lines.append(current)

    y = 40
    for line in lines[:3]:
        draw.text((8, y), line, fill=_TEXT_WHITE, font=font_sm)
        y += 16


def _save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "JPEG", quality=90)
    print(f"  Saved: {path.relative_to(Path(__file__).parent.parent)}")


# ---------------------------------------------------------------------------
# Scene generators
# ---------------------------------------------------------------------------


def gen_s01() -> None:
    """s01 — Hidden Pedestrian (truck occlusion at intersection)."""
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img)
    _base_road(d)
    # Large truck blocking right side
    d.rectangle([(360, _H // 2 + 20), (540, _H - 10)], fill=_TRUCK_DARK)
    d.rectangle([(370, _H // 2 - 20), (520, _H // 2 + 25)], fill=(40, 45, 50))  # cab
    # Partially visible pedestrian behind truck
    px = 530
    d.ellipse([(px - 8, _H // 2 + 30), (px + 8, _H // 2 + 50)], fill=(200, 160, 120))
    d.rectangle([(px - 6, _H // 2 + 50), (px + 6, _H // 2 + 100)], fill=(50, 80, 180))
    _label(d, "Road scene: Large truck partially blocking right lane. Pedestrian partially visible behind truck on right side.", "s01")
    _watermark(d)
    _save(img, _ROOT / "s01" / "frame_001.jpg")


def gen_s02() -> None:
    """s02 — Highway Merge (on-ramp approaching lane 1)."""
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img)
    _base_road(d)
    # Highway vehicle (left lane)
    d.rectangle([(200, _H // 2 + 40), (270, _H - 40)], fill=_CAR_YELLOW)
    # On-ramp vehicle (lower right — merging in)
    d.rectangle([(420, _H - 80), (490, _H - 20)], fill=(50, 200, 100))
    # On-ramp line (diagonal)
    d.line([(500, _H), (300, _H // 2 + 20)], fill=(200, 200, 50), width=4)
    # Merge conflict zone marker
    d.ellipse([(295, _H // 2 + 10), (325, _H // 2 + 40)], outline=_WARN_RED, width=3)
    _label(d, "Highway merge: Vehicle approaching on-ramp. Merge conflict zone ahead.", "s02")
    _watermark(d)
    _save(img, _ROOT / "s02" / "frame_001.jpg")


def gen_s07() -> None:
    """s07 — Road Debris (large object in right lane)."""
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img)
    _base_road(d)
    # Irregular debris shape in right lane
    d.polygon(
        [(370, _H - 60), (430, _H - 90), (470, _H - 55), (450, _H - 30), (390, _H - 25)],
        fill=_DEBRIS_COLOR,
    )
    # Warning chevron above debris
    d.polygon([(390, _H - 110), (420, _H - 95), (410, _H - 115)], fill=_WARN_RED)
    _label(d, "Highway scene: Large object/debris visible in right lane.", "s07")
    _watermark(d)
    _save(img, _ROOT / "s07" / "frame_001.jpg")


def gen_s08() -> None:
    """s08 — Conflicting Reports (road clear but alleged debris)."""
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img)
    _base_road(d)
    # Road looks clear — no obvious debris
    # Ghost outline where debris was alleged
    d.rectangle([(300, _H - 80), (380, _H - 30)], outline=_WARN_RED, width=2)
    # Question mark over alleged debris position
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        font = ImageFont.load_default()
    d.text((326, _H - 78), "?", fill=_WARN_RED, font=font)
    _label(d, "Highway scene: Lane 3 ahead. Road condition unclear.", "s08")
    _watermark(d)
    _save(img, _ROOT / "s08" / "frame_001.jpg")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating placeholder images...")
    gen_s01()
    gen_s02()
    gen_s07()
    gen_s08()
    print("Done.")
