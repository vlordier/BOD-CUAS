#!/usr/bin/env python3
"""Build a self-contained training-only airport pack from source JSON."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
MODALITIES = {"radar", "rf", "eo_ir", "acoustic", "adsb", "remote_id"}


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def required(source: dict[str, Any], key: str) -> Any:
    value = source.get(key)
    if value in (None, "", []):
        raise ValueError(f"source: missing {key}")
    return value


def ordered_bounds(source: dict[str, Any]) -> dict[str, float]:
    raw = required(source, "bounds")
    if not isinstance(raw, dict):
        raise ValueError("source.bounds must be an object")
    keys = ("min_latitude", "max_latitude", "min_longitude", "max_longitude")
    if not all(isinstance(raw.get(key), (int, float)) for key in keys):
        raise ValueError("source.bounds requires numeric latitude/longitude limits")
    if raw["min_latitude"] >= raw["max_latitude"] or raw["min_longitude"] >= raw["max_longitude"]:
        raise ValueError("source.bounds must be ordered")
    return {key: float(raw[key]) for key in keys}


def build(source_path: Path, output: Path) -> Path:
    source = read_object(source_path)
    icao = required(source, "icao")
    if not isinstance(icao, str) or not re.fullmatch(r"[A-Z]{4}", icao):
        raise ValueError("source.icao must be a four-letter uppercase ICAO code")
    iata = required(source, "iata")
    name = required(source, "name")
    country = required(source, "country")
    point = required(source, "reference_point")
    if not isinstance(point, dict) or not all(isinstance(point.get(k), (int, float)) for k in ("latitude", "longitude")):
        raise ValueError("source.reference_point requires numeric latitude and longitude")
    bounds = ordered_bounds(source)
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    identity = {"schema": "bod-cuas.airport-pack.identity", "version": VERSION, "icao": icao, "iata": iata, "name": name, "country": country, "coordinate_reference_system": source.get("coordinate_reference_system", "WGS84"), "reference_point": point, "display_bounds": bounds, "data_status": source.get("data_status", "synthetic_demo_context"), "authority_boundary": "context_only"}
    geo = source.get("geodata") or {}
    if not isinstance(geo, dict):
        raise ValueError("source.geodata must be an object")
    write_json(output / "identity.json", identity)
    write_json(output / "geodata-source.json", {"schema": "bod-cuas.airport-pack.geodata-source", "version": VERSION, "airport_icao": icao, "provenance": geo.get("provenance", "source supplied by pack author; not operationally certified"), "sources": geo.get("sources", []), "authority_boundary": "context_only"})
    layers = geo.get("layers", ["terrain", "buildings", "runways"])
    write_json(output / "visual-context.json", {"schema": "bod-cuas.airport-pack.visual-context", "version": VERSION, "airport_icao": icao, "bounds": bounds, "layers": layers, "assets": geo.get("assets", {}), "authority_boundary": "context_only"})
    write_json(output / "geodata.json", {"schema": "bod-cuas.airport-pack.geodata", "version": VERSION, "source_manifest": "geodata-source.json", "visual_context": "visual-context.json", "world3d": geo.get("world3d", {}), "layers": layers, "authority_boundary": "context_only"})

    raw_sensors = source.get("sensors") or [{"id": "sensor-demo-01", "modality": "radar", "label": "Synthetic sensor 01", "status": "simulated"}]
    if not isinstance(raw_sensors, list) or not raw_sensors:
        raise ValueError("source.sensors must be a non-empty array")
    sensors = []
    for index, item in enumerate(raw_sensors, 1):
        if not isinstance(item, dict) or item.get("modality") not in MODALITIES:
            raise ValueError(f"source.sensors[{index - 1}] has an unsupported modality")
        position = item.get("position", point)
        sensors.append({"id": item.get("id", f"sensor-{index:02d}"), "modality": item["modality"], "label": item.get("label", f"{item['modality']} sensor {index:02d}"), "latitude": position["latitude"], "longitude": position["longitude"], "altitude_m": position.get("altitude_m", 0), "source_id": item.get("source_id", f"{item['modality']}-source"), "status": item.get("status", "simulated")})
    write_json(output / "source-catalog.json", {"schema": "furia.cuas.source-catalog", "version": VERSION, "airport_icao": icao, "sources": [{"id": s["source_id"], "claim": f"{s['modality']} observation", "state": "training_simulator", "authority": "training_only"} for s in sensors]})
    write_json(output / "sensors.json", {"schema": "bod-cuas.airport-pack.sensors", "version": VERSION, "source_catalog": "source-catalog.json", "authority_boundary": "training_only", "sensors": sensors})

    raw_sectors = source.get("sectors") or [{"id": "airport", "label": "Airport context", "kind": "airfield", "protected_volume_ids": ["airport-context"]}]
    sectors = [{"id": s["id"], "label": s.get("label", s["id"]), "kind": s.get("kind", "sector"), "protected_volume_ids": s.get("protected_volume_ids", [])} for s in raw_sectors]
    volume_ids = sorted({v for s in sectors for v in s["protected_volume_ids"]})
    policy = "# Generated training-only protected-volume context\nauthority_boundary: training_only\nvolumes:\n" + "".join(f"  - id: {v}\n    state: context_only\n" for v in volume_ids)
    (output / "protected-volumes.yaml").write_text(policy, encoding="utf-8")
    write_json(output / "sectors.json", {"schema": "bod-cuas.airport-pack.sectors", "version": VERSION, "policy_source": "protected-volumes.yaml", "authority_boundary": "training_only", "sectors": sectors})

    raw_scenarios = source.get("scenarios") or [{"id": "baseline-surveillance", "kind": "synthetic", "status": "available"}]
    scenarios = [{"id": s["id"], "kind": s.get("kind", "synthetic"), "status": s.get("status", "available")} for s in raw_scenarios]
    write_json(output / "scenarios.json", {"schema": "bod-cuas.airport-pack.scenarios", "version": VERSION, "scenarios": scenarios})
    write_json(output / "catalogue.json", {"schema": "bod-cuas.airport-pack.capability-catalogue", "version": VERSION, "airport_icao": icao, "authority_boundary": "training_only", "sensors": [{"id": s["id"], "modality": s["modality"], "status": s["status"]} for s in sensors], "interceptors": source.get("interceptors", []), "matching": {"engine": "furia-cuas runtime", "inputs": ["threat", "weather", "availability", "civil_conflict"]}})
    write_json(output / "profile.json", {"schema": "bod-cuas.airport-operational-profile", "version": VERSION, "id": f"{icao.lower()}-profile", "icao": icao, "iata": iata, "name": name, "bounds": {"minLat": bounds["min_latitude"], "maxLat": bounds["max_latitude"], "minLon": bounds["min_longitude"], "maxLon": bounds["max_longitude"]}, "sensorSites": [{"featureId": s["id"]} for s in sensors], "noFlyZones": [{"featureId": v, "type": "context", "label": v} for v in volume_ids], "operationalMode": "training_replay", "liveAuthorityConnected": False})
    manifest = {"schema": "bod-cuas.airport-pack", "version": VERSION, "id": f"{icao.lower()}-airport-pack", "airport_icao": icao, "display_name": f"{name} · synthetic training pack", "authority_boundary": "training_only", "components": {key: f"{key}.json" for key in ("identity", "geodata", "sensors", "sectors", "scenarios")}, "profile": "profile.json", "catalogue": "catalogue.json"}
    write_json(output / "manifest.json", manifest)
    report = {"schema": "bod-cuas.airport-pack.validation-report", "version": VERSION, "status": "generated_pending_validation", "airport_icao": icao, "manifest": "manifest.json", "authority_boundary": "training_only", "checks": ["manifest contract", "component references", "bounds", "sensor positions", "sector policy references", "provenance"], "generated_at": datetime.now(timezone.utc).isoformat()}
    write_json(output / "validation-report.json", report)
    from validate_airport_pack import validate
    report["status"] = "validated"
    report["summary"] = validate(output / "manifest.json")
    write_json(output / "validation-report.json", report)
    return output / "manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(build(args.source.resolve(), args.output))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
