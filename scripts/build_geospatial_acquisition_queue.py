#!/usr/bin/env python3
"""Build an explicit, non-fabricating acquisition queue for airport packs."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def candidate_bbox(reference_point: dict[str, Any], radius_m: float) -> dict[str, float]:
    lat = float(reference_point["latitude"])
    lon = float(reference_point["longitude"])
    lat_delta = radius_m / 111_320.0
    lon_delta = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return {"south": lat - lat_delta, "west": lon - lon_delta, "north": lat + lat_delta, "east": lon + lon_delta}


def build_queue(inventory: dict[str, Any], root: Path, current_reference: dict[str, Any] | None = None, radius_m: float = 3000.0) -> dict[str, Any]:
    references = {entry["icao"]: entry for entry in (current_reference or {}).get("airports", [])}
    items = []
    for airport in inventory["airports"]:
        icao = airport["icao"]
        manifest = root / "data" / "geospatial" / icao.lower() / "manifest.json"
        if manifest.exists():
            status = "context_pack_present_needs_review"
            next_step = "run provenance validation and record review owner"
        else:
            status = "source_acquisition_required"
            next_step = "obtain an explicit airport bbox and current DEM/building sources"
        reference = references.get(icao)
        point = (reference or {}).get("reference_point")
        if point:
            status = "reference_ready_bbox_review" if not manifest.exists() else status
            next_step = "review candidate bbox, then acquire DEM/buildings and validate provenance"
        items.append({
            "icao": icao,
            "name": airport["name"],
            "iata": airport.get("iata"),
            "status": status,
            "pack_path": str(manifest.relative_to(root)) if manifest.exists() else None,
            "current_reference_status": (reference or {}).get("source_status"),
            "reference_point": point,
            "candidate_bbox_wgs84": candidate_bbox(point, radius_m) if point else None,
            "candidate_bbox_radius_m": radius_m if point else None,
            "candidate_bbox_status": "derived_for_review_only" if point else "missing_reference_point",
            "required_inputs": [
                "explicit_bbox_wgs84",
                "terrain_source_and_license",
                "building_source_and_height_quality",
                "retrieval_timestamp",
                "operational_authority_review_status",
            ],
            "recommended_sources": [
                {"kind": "terrain", "provider": "IGN Géoplateforme / RGE ALTI", "url": "https://geoservices.ign.fr/rgealti"},
                {"kind": "buildings", "provider": "IGN BD TOPO or OSM", "url": "https://geoservices.ign.fr/bdtopo"},
                {"kind": "aeronautical_reference", "provider": "SIA", "url": "https://www.sia.aviation-civile.gouv.fr/"},
            ],
            "next_step": next_step,
            "operational_claim": "none",
        })
    return {
        "schema": "bod-cuas.airport-geospatial-acquisition-queue",
        "version": "1.0.0",
        "source_inventory": inventory["source_id"],
        "inventory_status": inventory["status"],
        "policy": "never fabricate geometry from identity-only records",
        "summary": {
            "total": len(items),
            "packs_present": sum(item["pack_path"] is not None for item in items),
            "acquisition_required": sum(item["status"] == "source_acquisition_required" for item in items),
            "bbox_review_ready": sum(item["status"] == "reference_ready_bbox_review" for item in items),
        },
        "airports": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current-reference", type=Path, default=None)
    parser.add_argument("--radius-m", type=float, default=3000.0)
    args = parser.parse_args()
    root = (args.root or args.inventory.resolve().parents[2]).resolve()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if args.radius_m <= 0:
        parser.error("--radius-m doit être positif")
    current_reference = json.loads(args.current_reference.read_text(encoding="utf-8")) if args.current_reference else None
    result = build_queue(inventory, root, current_reference, args.radius_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
