#!/usr/bin/env python3
"""Index or selectively extract the verified LFBD Bati3D 2012 source archive.

The Bordeaux Metropole package is nested ZIP -> per-grid ZIP -> 3DS/JPEG.
This tool deliberately has no broad-extraction default: the source is a large
historical visual-context data set, not an airport-operational product.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import zipfile
from pathlib import Path

SUBTILE = re.compile(r"(?:^|/)tile_x(?P<x>\d+)y(?P<y>\d+)/tile_x\d+y\d+\.3ds$")
# Provider TO_DALLE_S calibration: HK / x55y117 begins at (1402600, 4187000).
GRID_ORIGIN_EASTING, GRID_ORIGIN_NORTHING, SUBTILE_METRES = 1_391_600, 4_163_600, 200


def subtile_record(outer_tile: str, member: str) -> dict[str, object] | None:
    match = SUBTILE.search(member)
    if not match:
        return None
    x, y = int(match["x"]), int(match["y"])
    easting = GRID_ORIGIN_EASTING + x * SUBTILE_METRES
    northing = GRID_ORIGIN_NORTHING + y * SUBTILE_METRES
    name = f"x{x}y{y}"
    return {"id": name, "outer_tile": outer_tile, "source_3ds": member,
            "texture_jpeg": str(Path(member).with_name(f"{name}.jpg")),
            "epsg3945_bbox": [easting, northing, easting + SUBTILE_METRES, northing + SUBTILE_METRES]}


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as raw:
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_archive(archive: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(archive) as outer:
        for info in outer.infolist():
            if info.filename.endswith(".zip"):
                outer_tile = Path(info.filename).stem
                with zipfile.ZipFile(io.BytesIO(outer.read(info))) as inner:
                    records.extend(record for member in inner.namelist()
                                   if (record := subtile_record(outer_tile, member)))
    return sorted(records, key=lambda item: str(item["id"]))


def extract_records(archive: Path, records: list[dict[str, object]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as outer:
        for outer_tile in sorted({str(item["outer_tile"]) for item in records}):
            with zipfile.ZipFile(io.BytesIO(outer.read(f"{outer_tile}.zip"))) as inner:
                for record in (item for item in records if item["outer_tile"] == outer_tile):
                    for member in (str(record["source_3ds"]), str(record["texture_jpeg"])):
                        target = output / str(record["id"]) / Path(member).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with inner.open(member) as source, target.open("wb") as destination:
                            shutil.copyfileobj(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("data/lfbd/bati3d/bati3d-lfbd-2012-3ds.zip"))
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--subtile", action="append", default=[])
    parser.add_argument("--extract-dir", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    if not archive.is_file():
        raise SystemExit(f"archive not found: {archive}")
    if bool(args.subtile) != bool(args.extract_dir):
        raise SystemExit("supply both --subtile and --extract-dir; broad extraction is refused")
    records = index_archive(archive)
    payload = {"schema": "furia.lfbd.bati3d-index", "version": "1.0.0",
               "source_archive": archive.name, "archive_sha256": source_sha256(archive),
               "crs": "EPSG:3945", "subtile_size_m": SUBTILE_METRES,
               "provenance": {"classification": "historical_open_context",
                              "display_label": "Bordeaux Metropole Bati3D (2012)",
                              "authority": "context_only",
                              "prohibited_claims": ["current airport layout", "obstacle authority", "live EO/IR imagery"]},
               "subtiles": records}
    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(json.dumps(payload, indent=2) + "\n")
    if args.subtile:
        wanted = set(args.subtile)
        selected = [item for item in records if item["id"] in wanted]
        missing = wanted - {str(item["id"]) for item in selected}
        if missing:
            raise SystemExit(f"requested subtiles absent from archive: {', '.join(sorted(missing))}")
        extract_records(archive, selected, args.extract_dir)
    print(f"indexed {len(records)} Bati3D subtiles -> {args.index}")


if __name__ == "__main__":
    main()
