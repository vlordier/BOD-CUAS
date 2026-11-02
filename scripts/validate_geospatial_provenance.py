#!/usr/bin/env python3
"""Validate provenance and structural quality gates for airport geodata."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def resolve(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"invalid or missing repository reference: {relative}")
    return path


def numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def validate_manifest(path: Path, repository_root: Path | None = None) -> list[str]:
    path = path.resolve()
    root = (repository_root or path.parents[2]).resolve()
    manifest = load(path)
    if manifest.get("schema") != "furia.cuas.airport-geospatial-context":
        raise ValueError("unexpected geospatial manifest schema")
    if manifest.get("authority") != "context_only":
        raise ValueError("geospatial data must be context_only")
    if not re.fullmatch(r"[A-Z]{4}", str(manifest.get("airport_icao", ""))):
        raise ValueError("airport_icao must be a four-letter ICAO code")
    box = manifest.get("bbox") or {}
    south, west = numeric(box.get("south"), "bbox.south"), numeric(box.get("west"), "bbox.west")
    north, east = numeric(box.get("north"), "bbox.north"), numeric(box.get("east"), "bbox.east")
    if not south < north or not west < east:
        raise ValueError("bbox must be ordered")
    if not isinstance(manifest.get("quality"), dict) or not manifest["quality"].get("terrain") or not manifest["quality"].get("buildings"):
        raise ValueError("quality metadata for terrain and buildings is required")
    provenance = manifest.get("provenance") or {}
    if not provenance.get("source_catalog") or not provenance.get("review_status"):
        raise ValueError("provenance source_catalog and review_status are required")

    terrain = load(resolve(path.parent, manifest["layers"]["terrain"]))
    samples = terrain.get("elevations")
    rows, cols = int(terrain.get("rows", 0)), int(terrain.get("cols", 0))
    if terrain.get("schema") != "furia.cuas.terrain-grid" or terrain.get("operational_status") != "context_only":
        raise ValueError("terrain schema/status is not a context-only DEM")
    if not isinstance(samples, list) or rows <= 1 or cols <= 1 or len(samples) != rows * cols:
        raise ValueError("terrain dimensions do not match elevation samples")
    # DEM grids are generated from decimal bbox endpoints and serialized as
    # JSON; allow sub-metre floating-point drift at the boundary, while still
    # rejecting genuinely misplaced samples.
    boundary_tolerance = 1e-6
    for index, sample in enumerate(samples):
        lon, lat = numeric(sample.get("lon"), f"terrain[{index}].lon"), numeric(sample.get("lat"), f"terrain[{index}].lat")
        if sample.get("valid", True):
            numeric(sample.get("z"), f"terrain[{index}].z")
        elif sample.get("z") is not None:
            raise ValueError(f"terrain[{index}] invalid sample must have null z")
        if not west - boundary_tolerance <= lon <= east + boundary_tolerance or not south - boundary_tolerance <= lat <= north + boundary_tolerance:
            raise ValueError(f"terrain[{index}] lies outside manifest bbox")

    buildings = json.loads(resolve(path.parent, manifest["layers"]["buildings"]).read_text(encoding="utf-8"))
    if buildings.get("type") != "FeatureCollection" or not isinstance(buildings.get("features"), list):
        raise ValueError("buildings must be a GeoJSON FeatureCollection")
    unknown_heights = 0
    for index, feature in enumerate(buildings["features"]):
        if feature.get("geometry", {}).get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"building[{index}] has unsupported geometry")
        stack = [feature["geometry"].get("coordinates", [])]
        while stack:
            item = stack.pop()
            if isinstance(item, list) and item and isinstance(item[0], list):
                stack.extend(item)
            elif isinstance(item, list) and len(item) >= 2:
                lon, lat = numeric(item[0], f"building[{index}].lon"), numeric(item[1], f"building[{index}].lat")
                if not west - boundary_tolerance <= lon <= east + boundary_tolerance or not south - boundary_tolerance <= lat <= north + boundary_tolerance:
                    raise ValueError(f"building[{index}] lies outside manifest bbox")
        if (feature.get("properties") or {}).get("height_m") is None:
            unknown_heights += 1
    if not (buildings.get("metadata") or {}).get("license"):
        raise ValueError("buildings metadata.license is required")
    resolve(path.parent, provenance["source_catalog"])
    return [f"{manifest['airport_icao']}: provenance valid", f"terrain={rows}x{cols}", f"buildings={len(buildings['features'])} (height unknown={unknown_heights})", "operational_status=context_only"]


def validate_registry(path: Path) -> list[str]:
    root = path.resolve().parent.parent.parent
    registry = load(path)
    if registry.get("schema") != "bod-cuas.france-airport-geospatial-registry" or registry.get("registry_status") != "partial_inventory":
        raise ValueError("registry must declare a partial inventory")
    inventory_path = resolve(root, registry.get("identity_inventory", ""))
    inventory = load(inventory_path)
    if inventory.get("status") != "historical_identity_inventory_only":
        raise ValueError("identity inventory must remain non-operational")
    inventory_airports = inventory.get("airports")
    if not isinstance(inventory_airports, list) or len(inventory_airports) < 1:
        raise ValueError("identity inventory must contain airport entries")
    inventory_codes = [entry.get("icao") for entry in inventory_airports]
    if any(not isinstance(code, str) or not re.fullmatch(r"[A-Z]{4}", code) for code in inventory_codes):
        raise ValueError("identity inventory contains an invalid ICAO code")
    if len(set(inventory_codes)) != len(inventory_codes):
        raise ValueError("identity inventory contains duplicate ICAO codes")
    airports = registry.get("airports")
    if not isinstance(airports, list):
        raise ValueError("registry.airports must be a list")
    inventory_sources = registry.get("inventory_sources")
    if not isinstance(inventory_sources, list) or not inventory_sources:
        raise ValueError("registry.inventory_sources must contain public references")
    for source in inventory_sources:
        if not all(isinstance(source.get(field), str) and source[field].strip() for field in ("id", "provider", "url", "status")):
            raise ValueError("registry inventory source metadata is incomplete")
        if not str(source["url"]).startswith("https://"):
            raise ValueError("registry inventory source URL must be HTTPS")
    seen = set()
    for entry in airports:
        icao = entry.get("icao")
        if not isinstance(icao, str) or not re.fullmatch(r"[A-Z]{4}", icao) or icao in seen:
            raise ValueError("registry ICAO values must be unique four-letter codes")
        seen.add(icao)
        pack = load(resolve(root, entry["pack_manifest"]))
        if pack.get("airport_icao") != icao:
            raise ValueError(f"{icao}: pack ICAO mismatch")
        validate_manifest(resolve(root, entry["geospatial_manifest"]), root)
    return [
        f"registry: {len(airports)} airport pack(s), explicitly partial",
        f"identity inventory: {len(inventory_airports)} historical airport entries; packs remain independently required",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    try:
        for line in validate_manifest(args.manifest):
            print(f"OK {line}")
        for line in validate_registry(args.registry):
            print(f"OK {line}")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
