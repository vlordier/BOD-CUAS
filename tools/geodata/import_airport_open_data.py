#!/usr/bin/env python3
"""Acquire context-only terrain/buildings for any airport.

This command deliberately requires the airport ICAO and bounding box. It never
derives an airport geometry from an identity record and never claims
operational obstacle or navigation authority.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from import_lfbd_open_data import (
    DEFAULT_ALTI_URL,
    DEFAULT_OVERPASS_URL,
    import_buildings,
    import_dem,
)


def build_manifest(icao: str, terrain: dict, buildings: dict) -> dict:
    return {
        "schema": "furia.cuas.airport-geospatial-context",
        "version": "1.0.0",
        "airport_icao": icao,
        "authority": "context_only",
        "bbox": terrain["bbox"],
        "layers": {"terrain": "terrain-grid.json", "buildings": "buildings.geojson"},
        "provenance": {
            "source_catalog": "source-catalog.json",
            "review_status": "pending_context_review",
            "retrieval_timestamp": terrain.get("retrieved_at", "unknown"),
        },
        "quality": {
            "terrain": {
                "rows": terrain.get("rows"),
                "cols": terrain.get("cols"),
                "resolution_approx_m": terrain.get("resolution_approx_m"),
                "valid_samples": terrain.get("quality", {}).get("valid_points"),
            },
            "buildings": {
                "features": len(buildings.get("features", [])),
                "height_unknown": sum(feature.get("properties", {}).get("height_m") is None for feature in buildings.get("features", [])),
            },
        },
        "sources": [terrain["source"], buildings["metadata"]["source"]],
        "license": [terrain["license"], buildings["metadata"]["license"]],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Contexte de simulation et de visualisation uniquement",
            "Ne remplace pas TOD, AIP, NOTAM, obstacle database ou validation aéroportuaire",
            "Les hauteurs absentes ou inférées doivent être traitées comme incertaines",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icao", required=True, help="code ICAO à quatre lettres")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--alti-url", default=DEFAULT_ALTI_URL)
    parser.add_argument("--overpass-url", default=DEFAULT_OVERPASS_URL)
    args = parser.parse_args()
    icao = args.icao.upper()
    if len(icao) != 4 or not icao.isalpha():
        parser.error("--icao doit être un code ICAO de quatre lettres")
    if args.rows < 2 or args.cols < 2:
        parser.error("--rows et --cols doivent être au moins égaux à 2")
    south, west, north, east = args.bbox
    if not (south < north and west < east):
        parser.error("--bbox doit être ordonnée SOUTH WEST NORTH EAST")
    args.output.mkdir(parents=True, exist_ok=True)
    terrain = import_dem((south, west, north, east), args.rows, args.cols, args.alti_url)
    terrain["operational_status"] = "context_only"
    try:
        buildings = import_buildings((south, west, north, east), args.overpass_url)
    except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
        buildings = {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {
                "source": "OpenStreetMap contributors",
                "source_url": "https://www.openstreetmap.org/",
                "license": "ODbL 1.0",
                "overpass_url": args.overpass_url,
                "retrieved_at": terrain.get("retrieved_at"),
                "limitations": [
                    f"Import bâtiments différé : {error}",
                    "Couche absente ; ne pas interpréter comme absence de bâtiments",
                    "Relancer avec une instance Overpass locale ou une extraction BD TOPO/BDNB",
                ],
            },
        }
    (args.output / "terrain-grid.json").write_text(json.dumps(terrain, indent=2) + "\n", encoding="utf-8")
    (args.output / "buildings.geojson").write_text(json.dumps(buildings, indent=2) + "\n", encoding="utf-8")
    (args.output / "source-catalog.json").write_text(json.dumps({
        "schema": "furia.cuas.source-catalog",
        "version": "1.0.0",
        "airport_icao": icao,
        "authority": "context_only",
        "sources": [
            {"id": "terrain", "provider": terrain["source"], "url": terrain["source_url"], "license": terrain["license"]},
            {"id": "buildings", "provider": buildings["metadata"]["source"], "url": buildings["metadata"]["source_url"], "license": buildings["metadata"]["license"]},
        ],
    }, indent=2) + "\n", encoding="utf-8")
    (args.output / "manifest.json").write_text(json.dumps(build_manifest(icao, terrain, buildings), indent=2) + "\n", encoding="utf-8")
    print(f"Imported {icao} context ({len(terrain['elevations'])} terrain points, {len(buildings['features'])} buildings) into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
