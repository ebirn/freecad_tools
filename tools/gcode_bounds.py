#!/usr/bin/env python3
"""Report XY extents from a G-code file."""

import argparse
import json
import math
import re
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Report XY extents from G-code")
    parser.add_argument("gcode_file", type=Path, help="Path to .gcode file")
    return parser.parse_args()


def compute_bounds(gcode_file):
    x = None
    y = None
    xmin = math.inf
    ymin = math.inf
    xmax = -math.inf
    ymax = -math.inf
    rx = re.compile(r"\bX(-?\d+(?:\.\d+)?)")
    ry = re.compile(r"\bY(-?\d+(?:\.\d+)?)")

    with gcode_file.open("rb") as raw:
        sample = raw.read(4096)
        if b"\x00" in sample:
            return _compute_binary_bounds(gcode_file)

    with gcode_file.open(errors="ignore", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.lstrip()
            if not stripped.startswith(("G0", "G00", "G1", "G01")):
                continue
            mx = rx.search(stripped)
            my = ry.search(stripped)
            if mx:
                x = float(mx.group(1))
            if my:
                y = float(my.group(1))
            if x is not None and y is not None:
                xmin = min(xmin, x)
                xmax = max(xmax, x)
                ymin = min(ymin, y)
                ymax = max(ymax, y)

    if xmin is math.inf:
        raise ValueError("No G0/G1 XY coordinates found in file")

    return xmin, ymin, xmax, ymax, "toolpath"


def _compute_binary_bounds(gcode_file):
    """Compute bounds from Prusa binary G-code metadata when available."""
    data = gcode_file.read_bytes()
    decoded = data.decode("utf-8", errors="ignore")
    marker = "objects_info="
    start = decoded.find(marker)
    if start < 0:
        raise ValueError("Binary G-code detected, but objects_info metadata was not found")

    line_end = decoded.find("\n", start)
    if line_end < 0:
        line_end = len(decoded)
    payload = decoded[start + len(marker) : line_end].strip()
    try:
        info = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Binary G-code objects_info metadata is invalid JSON: {exc}") from exc

    objects = info.get("objects", [])
    points = []
    for obj in objects:
        for xy in obj.get("polygon", []):
            if isinstance(xy, list) and len(xy) >= 2:
                points.append((float(xy[0]), float(xy[1])))

    if not points:
        raise ValueError("Binary G-code objects_info metadata did not contain polygon coordinates")

    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return min(xs), min(ys), max(xs), max(ys), "metadata"


def main():
    args = parse_args()
    try:
        xmin, ymin, xmax, ymax, source = compute_bounds(args.gcode_file)
    except ValueError as exc:
        print(f"file={args.gcode_file}")
        print(f"WARNING: {exc}")
        return

    print(f"file={args.gcode_file}")
    print(f"source={source}")
    print(f"XY min=({xmin:.2f},{ymin:.2f}) max=({xmax:.2f},{ymax:.2f}) size=({xmax - xmin:.2f},{ymax - ymin:.2f})")
    if xmin < 0 or ymin < 0:
        print("WARNING: Negative XY coordinates detected; toolpath may be outside printable area.")
    else:
        print("OK: XY coordinates are non-negative.")


if __name__ == "__main__":
    main()
