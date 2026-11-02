#!/usr/bin/env python3
"""Import public LFBD terrain and building context for simulation.

Outputs a portable, context-only dataset. It is not aviation obstacle data.
Sources: IGN Géoplateforme RGE ALTI and OpenStreetMap via Overpass.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BBOX = (44.80, -0.76, 44.86, -0.68)
DEFAULT_ALTI_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
DEFAULT_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"


def fetch_json(url: str, *, method: str = "GET", body: bytes | None = None) -> dict:
    request = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "Furia-CUAS-geodata-importer/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status} from {url}")
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from error


def grid_points(bbox: tuple[float, float, float, float], rows: int, cols: int) -> list[tuple[float, float]]:
    south, west, north, east = bbox
    return [(west + (east - west) * col / max(1, cols - 1), south + (north - south) * row / max(1, rows - 1)) for row in range(rows) for col in range(cols)]


def import_dem(bbox: tuple[float, float, float, float], rows: int, cols: int, endpoint: str) -> dict:
    points = grid_points(bbox, rows, cols)
    elevations: list[dict] = []
    for start in range(0, len(points), 5000):
        batch = points[start : start + 5000]
        query = urllib.parse.urlencode({"lon": "|".join(f"{lon:.8f}" for lon, _ in batch), "lat": "|".join(f"{lat:.8f}" for _, lat in batch), "resource": "ign_rge_alti_wld", "delimiter": "|", "indent": "false", "measures": "false", "zonly": "false"})
        elevations.extend(fetch_json(f"{endpoint}?{query}").get("elevations", []))
        if start + 5000 < len(points):
            time.sleep(0.25)
    samples = []
    for item in elevations:
        try:
            z = float(item.get("z", -99999))
        except (TypeError, ValueError):
            z = -99999.0
        samples.append({**item, "z": z if z > -90000 else None, "valid": z > -90000})
    valid_count = sum(sample["valid"] for sample in samples)
    return {"schema": "furia.cuas.terrain-grid", "version": "1.0.0", "source": "IGN Géoplateforme · RGE ALTI", "source_url": endpoint, "resource": "ign_rge_alti_wld", "license": "Licence ouverte / Etalab", "bbox": {"south": bbox[0], "west": bbox[1], "north": bbox[2], "east": bbox[3]}, "rows": rows, "cols": cols, "resolution_approx_m": min((bbox[2] - bbox[0]) * 111000 / max(1, rows - 1), (bbox[3] - bbox[1]) * 79000 / max(1, cols - 1)), "elevations": samples, "quality": {"requested_points": len(points), "returned_points": len(elevations), "valid_points": valid_count, "missing_points": len(points) - valid_count}, "retrieved_at": datetime.now(timezone.utc).isoformat(), "limitations": ["Échantillonnage de démonstration, pas un MNT opérationnel", "Précision héritée de la ressource IGN sélectionnée", f"{len(points) - valid_count} cellules sans altitude valide"]}


def building_height(tags: dict) -> float:
    raw = str(tags.get("height", "")).replace(",", ".").replace("m", "").strip()
    try:
        if raw:
            return max(2.5, float(raw))
    except ValueError:
        pass
    try:
        return max(2.5, float(tags.get("building:levels", 1)) * 3.1)
    except (TypeError, ValueError):
        return 3.0


def import_buildings(bbox: tuple[float, float, float, float], endpoint: str) -> dict:
    south, west, north, east = bbox
    query = f"[out:json][timeout:90];way[building]({south},{west},{north},{east});out geom tags;"
    try:
        payload = fetch_json(endpoint, method="POST", body=query.encode("utf-8"))
    except (RuntimeError, urllib.error.URLError, TimeoutError):
        if "overpass-api.de" not in endpoint:
            raise
        payload = fetch_json("https://overpass.kumi.systems/api/interpreter", method="POST", body=query.encode("utf-8"))
    features = []
    excluded_out_of_bbox = 0
    for element in payload.get("elements", []):
        geometry = element.get("geometry", [])
        if len(geometry) < 3:
            continue
        coordinates = [[float(point["lon"]), float(point["lat"])] for point in geometry]
        if any(not (west <= lon <= east and south <= lat <= north) for lon, lat in coordinates):
            excluded_out_of_bbox += 1
            continue
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        tags = element.get("tags", {})
        features.append({"type": "Feature", "id": f"osm-{element.get('type', 'way')}-{element.get('id')}", "properties": {"height_m": building_height(tags), "levels": tags.get("building:levels"), "source": "OpenStreetMap", "osm_id": element.get("id")}, "geometry": {"type": "Polygon", "coordinates": [coordinates]}})
    return {"type": "FeatureCollection", "features": features, "metadata": {"source": "OpenStreetMap contributors", "source_url": "https://www.openstreetmap.org/", "license": "ODbL 1.0", "overpass_url": endpoint, "retrieved_at": datetime.now(timezone.utc).isoformat(), "excluded_out_of_bbox": excluded_out_of_bbox, "limitations": ["Hauteurs manquantes inférées à partir des niveaux ou d’une valeur prudente", "Données collaboratives à contrôler avant tout usage opérationnel", f"{excluded_out_of_bbox} géométries traversant l’emprise ont été exclues"]}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/geospatial/lfbd"))
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--alti-url", default=DEFAULT_ALTI_URL)
    parser.add_argument("--overpass-url", default=DEFAULT_OVERPASS_URL)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    terrain = import_dem(DEFAULT_BBOX, args.rows, args.cols, args.alti_url)
    try:
        buildings = import_buildings(DEFAULT_BBOX, args.overpass_url)
    except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
        # Overpass is a shared public service and can be temporarily busy. Keep
        # the valid IGN terrain result and make the missing layer explicit.
        buildings = {"type": "FeatureCollection", "features": [], "metadata": {"source": "OpenStreetMap contributors", "source_url": "https://www.openstreetmap.org/", "license": "ODbL 1.0", "overpass_url": args.overpass_url, "retrieved_at": datetime.now(timezone.utc).isoformat(), "limitations": [f"Import bâtiment reporté : {error}", "Utiliser une instance Overpass locale ou l’extraction BD TOPO/BDNB pour compléter la couche"]}}
    (args.output / "terrain-grid.json").write_text(json.dumps(terrain, indent=2) + "\n", encoding="utf-8")
    (args.output / "buildings.geojson").write_text(json.dumps(buildings, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema": "furia.cuas.airport-geospatial-context", "version": "1.0.0", "airport_icao": "LFBD", "authority": "context_only", "bbox": terrain["bbox"], "layers": {"terrain": "terrain-grid.json", "buildings": "buildings.geojson"}, "sources": [terrain["source"], buildings["metadata"]["source"]], "license": [terrain["license"], buildings["metadata"]["license"]], "retrieved_at": datetime.now(timezone.utc).isoformat(), "limitations": ["Contexte de simulation et de visualisation uniquement", "Ne remplace pas TOD, AIP, NOTAM, obstacle database ou validation aéroportuaire"]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Imported LFBD terrain ({len(terrain['elevations'])} points) and buildings ({len(buildings['features'])} features) into {args.output}")


if __name__ == "__main__":
    main()
