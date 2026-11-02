#!/usr/bin/env python3
"""Build a north-up LFBD context mosaic from the original Bati3D textures.

The JPEG paired with each 3DS subtile is an orthographic ground texture.  The
3D meshes must never be rendered in perspective and reused as a flat map: that
introduces parallax, black voids and false spatial relationships.  This tool
reads the verified nested archive directly and downsamples each source tile
before assembly so the browser artefact stays bounded.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


TILE_ID = re.compile(r"^x(?P<x>\d+)y(?P<y>\d+)$")


def parse_tile_id(tile_id: str) -> tuple[int, int]:
    match = TILE_ID.fullmatch(tile_id)
    if not match:
        raise ValueError(f"invalid Bati3D tile id: {tile_id}")
    return int(match["x"]), int(match["y"])


def selected_records(
    records: list[dict[str, object]], min_x: int, max_x: int, min_y: int, max_y: int
) -> list[dict[str, object]]:
    selected = [
        record
        for record in records
        if min_x <= parse_tile_id(str(record["id"]))[0] <= max_x
        and min_y <= parse_tile_id(str(record["id"]))[1] <= max_y
    ]
    expected = {f"x{x}y{y}" for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)}
    actual = {str(record["id"]) for record in selected}
    if missing := expected - actual:
        raise ValueError(f"incomplete mosaic selection; missing {', '.join(sorted(missing))}")
    return selected


def mosaic_position(tile_id: str, min_x: int, max_y: int, tile_pixels: int) -> tuple[int, int]:
    """Return a north-up raster position: east right, north up."""
    x, y = parse_tile_id(tile_id)
    return (x - min_x) * tile_pixels, (max_y - y) * tile_pixels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("data/lfbd/bati3d/bati3d-lfbd-2012-3ds.zip"))
    parser.add_argument("--index", type=Path, default=Path("data/lfbd/bati3d/index.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--min-x", type=int, default=64)
    parser.add_argument("--max-x", type=int, default=89)
    parser.add_argument("--min-y", type=int, default=110)
    parser.add_argument("--max-y", type=int, default=134)
    parser.add_argument("--tile-pixels", type=int, default=96)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_x > args.max_x or args.min_y > args.max_y or args.tile_pixels < 16:
        raise SystemExit("invalid mosaic extent or tile resolution")
    index = json.loads(args.index.read_text())
    records = selected_records(index["subtiles"], args.min_x, args.max_x, args.min_y, args.max_y)
    by_outer: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_outer[str(record["outer_tile"])].append(record)

    width = (args.max_x - args.min_x + 1) * args.tile_pixels
    height = (args.max_y - args.min_y + 1) * args.tile_pixels
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lfbd-orthomosaic-") as temporary:
        temporary_path = Path(temporary)
        extracted: dict[str, Path] = {}
        with zipfile.ZipFile(args.archive) as outer:
            for outer_tile, outer_records in sorted(by_outer.items()):
                with zipfile.ZipFile(BytesIO(outer.read(f"{outer_tile}.zip"))) as nested:
                    for record in outer_records:
                        target = temporary_path / f"{record['id']}.jpg"
                        target.write_bytes(nested.read(str(record["texture_jpeg"])))
                        extracted[str(record["id"])] = target
        rows: list[str] = []
        for y in range(args.max_y, args.min_y - 1, -1):
            row = temporary_path / f"row-{y}.miff"
            row_inputs = [str(extracted[f"x{x}y{y}"]) for x in range(args.min_x, args.max_x + 1)]
            subprocess.run(
                ["magick", *row_inputs, "-filter", "Lanczos", "-resize", f"{args.tile_pixels}x{args.tile_pixels}!", "+append", str(row)],
                check=True,
            )
            rows.append(str(row))
        subprocess.run(["magick", *rows, "-append", "-quality", "88", str(args.output.resolve())], check=True)
        dimensions = subprocess.run(
            ["magick", "identify", "-format", "%wx%h", str(args.output.resolve())],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if dimensions != f"{width}x{height}":
            raise SystemExit(f"unexpected mosaic dimensions: {dimensions}; expected {width}x{height}")

    west = min(int(record["epsg3945_bbox"][0]) for record in records)
    south = min(int(record["epsg3945_bbox"][1]) for record in records)
    east = max(int(record["epsg3945_bbox"][2]) for record in records)
    north = max(int(record["epsg3945_bbox"][3]) for record in records)
    manifest = {
        "schema": "furia.lfbd.bati3d-orthomosaic",
        "version": "1.0.0",
        "source": "Bordeaux Metropole Bati3D (2012) ground textures",
        "authority": "context_only",
        "orientation": "north_up",
        "tile_count": len(records),
        "tile_range": {"min_x": args.min_x, "max_x": args.max_x, "min_y": args.min_y, "max_y": args.max_y},
        "epsg3945_bbox": [west, south, east, north],
        "pixel_dimensions": [width, height],
        "prohibited_claims": ["current airport layout", "operational airport truth", "live imagery"],
    }
    manifest_output = args.manifest_output or args.output.with_suffix(".json")
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built north-up LFBD orthomosaic ({len(records)} tiles, {width}x{height}) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
