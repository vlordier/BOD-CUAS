#!/usr/bin/env python3
"""Acquire context-only DEM/building layers for airports with a public reference.

The script deliberately produces a pack only when both public layers are
retrieved and structurally valid.  A reference coordinate is not treated as
an airport boundary: the derived bbox is recorded as ``pending_context_review``
and must be reviewed before any operational use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IGN_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
OSM_URL = "https://api.openstreetmap.org/api/0.6/map"
VERSION = "1.0.0"


def bbox(point: dict[str, Any], radius_m: float) -> dict[str, float]:
    lat = float(point["latitude"])
    lon = float(point["longitude"])
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return {"south": lat - dlat, "west": lon - dlon, "north": lat + dlat, "east": lon + dlon}


def get(url: str, params: dict[str, Any], timeout: float) -> tuple[bytes, str]:
    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}"
    request = urllib.request.Request(request_url, headers={"User-Agent": "BOD-CUAS-context-acquirer/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                return payload, request_url
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1)
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 3:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def terrain_layer(box: dict[str, float], rows: int, cols: int, timeout: float) -> tuple[dict[str, Any], list[str]]:
    elevations = []
    urls = []
    for row in range(rows):
        lat = box["south"] + (box["north"] - box["south"]) * row / (rows - 1)
        for col in range(cols):
            lon = box["west"] + (box["east"] - box["west"]) * col / (cols - 1)
            raw, url = get(IGN_URL, {"lon": f"{lon:.8f}", "lat": f"{lat:.8f}", "resource": "ign_rge_alti_wld"}, timeout)
            value = json.loads(raw.decode("utf-8"))
            point = (value.get("elevations") or [None])[0]
            if not isinstance(point, dict) or not isinstance(point.get("z"), (int, float)):
                raise ValueError(f"IGN returned no elevation for {lat},{lon}")
            elevations.append({"lon": float(point.get("lon", lon)), "lat": float(point.get("lat", lat)), "z": float(point["z"]), "acc": point.get("acc", "unknown"), "valid": True})
            urls.append(url)
            time.sleep(0.04)
    return {
        "schema": "furia.cuas.terrain-grid",
        "version": VERSION,
        "operational_status": "context_only",
        "source": "IGN Géoplateforme · RGE ALTI",
        "source_url": IGN_URL,
        "resource": "ign_rge_alti_wld",
        "license": "Licence ouverte / Etalab",
        "bbox": box,
        "rows": rows,
        "cols": cols,
        "resolution_approx_m": (box["north"] - box["south"]) * 111_320 / (rows - 1),
        "elevations": elevations,
    }, urls


def buildings_layer(box: dict[str, float], timeout: float) -> tuple[dict[str, Any], str, str]:
    raw, url = get(OSM_URL, {"bbox": f'{box["west"]},{box["south"]},{box["east"]},{box["north"]}'}, timeout)
    root = ET.fromstring(raw)
    nodes = {node.attrib["id"]: (float(node.attrib["lon"]), float(node.attrib["lat"])) for node in root.findall("node")}
    features = []
    for way in root.findall("way"):
        tags = {tag.attrib.get("k"): tag.attrib.get("v", "") for tag in way.findall("tag")}
        if "building" not in tags:
            continue
        coordinates = [nodes[ref.attrib["ref"]] for ref in way.findall("nd") if ref.attrib.get("ref") in nodes]
        if len(coordinates) < 4:
            continue
        # Keep the pack strictly inside the declared context bbox.  Ways that
        # cross the boundary require a real polygon clipper and are excluded
        # rather than silently storing geometry outside the provenance box.
        if any(not (box["west"] <= lon <= box["east"] and box["south"] <= lat <= box["north"]) for lon, lat in coordinates):
            continue
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        properties: dict[str, Any] = {"osm_id": way.attrib.get("id"), "building": tags.get("building")}
        if tags.get("building:levels"):
            properties["building_levels"] = tags["building:levels"]
        if tags.get("height"):
            properties["height_m"] = tags["height"]
        features.append({"type": "Feature", "id": way.attrib.get("id"), "properties": properties, "geometry": {"type": "Polygon", "coordinates": [[list(point) for point in coordinates]]}})
    return {"type": "FeatureCollection", "features": features, "metadata": {"source": "OpenStreetMap contributors", "source_url": "https://www.openstreetmap.org/", "license": "ODbL 1.0", "overpass_url": OSM_URL}}, url, sha256(raw)


def acquire(icao: str, reference: dict[str, Any], output_root: Path, radius_m: float, timeout: float) -> Path:
    point = reference.get("reference_point")
    if not point:
        raise ValueError(f"{icao}: no current public reference point")
    box = bbox(point, radius_m)
    terrain, terrain_urls = terrain_layer(box, 4, 4, timeout)
    buildings, buildings_url, buildings_hash = buildings_layer(box, timeout)
    retrieved = datetime.now(timezone.utc).isoformat()
    directory = output_root / icao.lower()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "terrain-grid.json").write_text(json.dumps(terrain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "buildings.geojson").write_text(json.dumps(buildings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    catalog = {"schema": "furia.cuas.source-catalog", "version": VERSION, "airport_icao": icao, "authority": "context_only", "sources": [{"id": "terrain", "provider": "IGN Géoplateforme · RGE ALTI", "url": IGN_URL, "license": "Licence ouverte / Etalab", "request_count": len(terrain_urls), "request_sha256": sha256("\n".join(terrain_urls).encode())}, {"id": "buildings", "provider": "OpenStreetMap contributors", "url": buildings_url, "license": "ODbL 1.0", "response_sha256": buildings_hash}]}
    (directory / "source-catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema": "furia.cuas.airport-geospatial-context", "version": VERSION, "airport_icao": icao, "authority": "context_only", "bbox": box, "layers": {"terrain": "terrain-grid.json", "buildings": "buildings.geojson"}, "provenance": {"source_catalog": "source-catalog.json", "review_status": "pending_context_review", "retrieval_timestamp": retrieved, "bbox_status": "derived_from_public_reference_point_pending_review"}, "quality": {"terrain": {"rows": terrain["rows"], "cols": terrain["cols"], "resolution_approx_m": terrain["resolution_approx_m"], "valid_samples": len(terrain["elevations"])}, "buildings": {"features": len(buildings["features"]), "height_unknown": sum("height_m" not in f["properties"] for f in buildings["features"])}}, "sources": ["IGN Géoplateforme · RGE ALTI", "OpenStreetMap contributors"], "license": ["Licence ouverte / Etalab", "ODbL 1.0"], "retrieved_at": retrieved, "limitations": ["Emprise dérivée du point de référence public : revue requise", "Contexte de simulation et de visualisation uniquement", "Ne remplace pas TOD, AIP, NOTAM, obstacle database ou validation aéroportuaire", "Les hauteurs absentes ou inférées doivent être traitées comme incertaines"]}
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--icao", action="append")
    parser.add_argument("--radius-m", type=float, default=3000.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    references = {item["icao"]: item for item in json.loads(args.reference.read_text(encoding="utf-8"))["airports"]}
    targets = args.icao or [icao for icao, item in references.items() if not (args.output_root / icao.lower() / "manifest.json").exists()]
    failures = []
    for icao in targets:
        try:
            print(acquire(icao, references[icao], args.output_root, args.radius_m, args.timeout))
        except Exception as error:  # acquisition must report, never fabricate a pack
            failures.append({"icao": icao, "error": str(error)})
            print(f"SKIP {icao}: {error}")
    if failures:
        print(json.dumps({"failed": failures}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
