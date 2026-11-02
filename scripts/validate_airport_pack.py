#!/usr/bin/env python3
"""Validate a BOD-CUAS airport-pack without third-party dependencies."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MODALITIES = {"radar", "rf", "eo_ir", "acoustic", "adsb", "remote_id"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def resolve(base: Path, reference: str, repository_root: Path) -> Path:
    path = (base / reference).resolve()
    if repository_root.resolve() not in path.parents and path != repository_root.resolve():
        raise ValueError(f"reference escapes BOD-CUAS repository: {reference}")
    if not path.is_file():
        raise ValueError(f"missing referenced file: {reference}")
    return path


def require(value: Any, name: str) -> None:
    if value in (None, "", []):
        raise ValueError(f"missing {name}")


def unique_ids(items: list[dict[str, Any]], label: str) -> None:
    ids = [item.get("id") for item in items]
    if any(not item_id for item_id in ids):
        raise ValueError(f"{label}: every item needs an id")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label}: ids must be unique")


def validate(manifest_path: Path) -> list[str]:
    manifest_path = manifest_path.resolve()
    pack_root = manifest_path.parent
    repository_root = next(
        (parent for parent in manifest_path.parents if (parent / "contracts").is_dir()),
        None,
    )
    if repository_root is None:
        raise ValueError("manifest must be inside a BOD-CUAS repository")
    manifest = load_json(manifest_path)
    if manifest.get("schema") != "bod-cuas.airport-pack":
        raise ValueError("manifest schema must be bod-cuas.airport-pack")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", ""))):
        raise ValueError("manifest version must be semantic X.Y.Z")
    require(manifest.get("id"), "manifest id")
    if manifest.get("authority_boundary") not in {"context_only", "training_only"}:
        raise ValueError("manifest authority_boundary must be context_only or training_only")

    components = manifest.get("components")
    if not isinstance(components, dict) or set(components) != {"identity", "geodata", "sensors", "sectors", "scenarios"}:
        raise ValueError("manifest components must separate identity, geodata, sensors, sectors and scenarios")
    files = {key: resolve(pack_root, value, repository_root) for key, value in components.items() if isinstance(value, str)}
    if len(files) != 5:
        raise ValueError("all component references must be relative strings")
    for key in ("profile", "catalogue"):
        if key in manifest:
            resolve(pack_root, manifest[key], repository_root)

    identity = load_json(files["identity"])
    if identity.get("schema") != "bod-cuas.airport-pack.identity":
        raise ValueError("identity has an unexpected schema")
    icao = identity.get("icao")
    require(icao, "identity.icao")
    if not re.fullmatch(r"[A-Z]{4}", icao):
        raise ValueError("identity.icao must be a four-letter ICAO code")
    require(identity.get("iata"), "identity.iata")
    bounds = identity.get("display_bounds")
    if not isinstance(bounds, dict) or not (bounds["min_latitude"] < bounds["max_latitude"] and bounds["min_longitude"] < bounds["max_longitude"]):
        raise ValueError("identity.display_bounds must be ordered")

    geodata = load_json(files["geodata"])
    if geodata.get("schema") != "bod-cuas.airport-pack.geodata":
        raise ValueError("geodata has an unexpected schema")
    resolve(files["geodata"].parent, geodata["source_manifest"], repository_root)
    resolve(files["geodata"].parent, geodata["visual_context"], repository_root)
    if geodata.get("authority_boundary") != "context_only":
        raise ValueError("geodata must be context_only")

    sensors = load_json(files["sensors"])
    if sensors.get("schema") != "bod-cuas.airport-pack.sensors":
        raise ValueError("sensors has an unexpected schema")
    resolve(files["sensors"].parent, sensors["source_catalog"], repository_root)
    sensor_items = sensors.get("sensors")
    if not isinstance(sensor_items, list) or not sensor_items:
        raise ValueError("sensors.sensors must be non-empty")
    unique_ids(sensor_items, "sensors")
    for sensor in sensor_items:
        if sensor.get("modality") not in MODALITIES:
            raise ValueError(f"sensor {sensor.get('id')}: unsupported modality")
        if not all(isinstance(sensor.get(key), (int, float)) for key in ("latitude", "longitude", "altitude_m")):
            raise ValueError(f"sensor {sensor.get('id')}: position must be numeric")
        if not (bounds["min_latitude"] <= sensor["latitude"] <= bounds["max_latitude"] and bounds["min_longitude"] <= sensor["longitude"] <= bounds["max_longitude"]):
            raise ValueError(f"sensor {sensor.get('id')}: position outside airport bounds")

    sectors = load_json(files["sectors"])
    if sectors.get("schema") != "bod-cuas.airport-pack.sectors":
        raise ValueError("sectors has an unexpected schema")
    policy_path = resolve(files["sectors"].parent, sectors["policy_source"], repository_root)
    policy_text = policy_path.read_text(encoding="utf-8")
    sector_items = sectors.get("sectors")
    if not isinstance(sector_items, list) or not sector_items:
        raise ValueError("sectors.sectors must be non-empty")
    unique_ids(sector_items, "sectors")
    for sector in sector_items:
        for volume_id in sector.get("protected_volume_ids", []):
            if not re.search(rf"(?m)^\s*- id: {re.escape(volume_id)}\s*$", policy_text):
                raise ValueError(f"sector {sector['id']}: unknown protected volume {volume_id}")

    scenarios = load_json(files["scenarios"])
    if scenarios.get("schema") != "bod-cuas.airport-pack.scenarios":
        raise ValueError("scenarios has an unexpected schema")
    scenario_items = scenarios.get("scenarios")
    if not isinstance(scenario_items, list) or not scenario_items:
        raise ValueError("scenarios.scenarios must be non-empty")
    unique_ids(scenario_items, "scenarios")
    for scenario in scenario_items:
        for key in ("entrypoint", "timeline", "fixture"):
            if key in scenario:
                resolve(files["scenarios"].parent, scenario[key], repository_root)

    return [
        f"{manifest['id']}: {icao}",
        f"components=identity,geodata,sensors,sectors,scenarios",
        f"sensors={len(sensor_items)} sectors={len(sector_items)} scenarios={len(scenario_items)}",
        "authority_boundary=training_only/context_only",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        for line in validate(args.manifest):
            print(f"OK {line}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
