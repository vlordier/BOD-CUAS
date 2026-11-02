#!/usr/bin/env python3
"""Resolve a generic BOD-CUAS airport-pack into runner-ready data.

The resolver deliberately knows only the airport-pack contract.  It does not
contain an airport code, a demo scenario name, or an operational authority.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


COMPONENTS = ("identity", "geodata", "sensors", "sectors", "scenarios")


def _repository_root(manifest_path: Path) -> Path:
    for parent in (manifest_path.parent, *manifest_path.parents):
        if (parent / "contracts" / "airport-pack.schema.json").is_file():
            return parent
    raise ValueError("manifest must be inside a BOD-CUAS repository")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _resolve_file(base: Path, reference: str, repository_root: Path) -> Path:
    if not isinstance(reference, str) or not reference or reference.startswith(("/", "\\")):
        raise ValueError(f"invalid relative reference: {reference!r}")
    path = (base / reference).resolve()
    root = repository_root.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"reference escapes BOD-CUAS repository: {reference}")
    if not path.is_file():
        raise ValueError(f"missing referenced file: {reference}")
    return path


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_airport_pack(manifest_path: str | Path) -> dict[str, Any]:
    """Return a validated, self-contained pack for a generic runner.

    Component source paths are repository-relative and every component is
    embedded as JSON data. Secondary references (geodata assets, sensor
    catalogue, policy, and scenario fixtures) remain explicit and resolved so
    a runner can load or report them without knowing the pack layout.
    """
    manifest_file = Path(manifest_path).resolve()
    repository_root = _repository_root(manifest_file)
    manifest = _read_json(manifest_file)
    if manifest.get("schema") != "bod-cuas.airport-pack":
        raise ValueError("manifest schema must be bod-cuas.airport-pack")
    components = manifest.get("components")
    if not isinstance(components, dict) or set(components) != set(COMPONENTS):
        raise ValueError("manifest components must contain identity, geodata, sensors, sectors and scenarios")

    files: dict[str, Path] = {
        key: _resolve_file(manifest_file.parent, components[key], repository_root)
        for key in COMPONENTS
    }
    data = {key: _read_json(files[key]) for key in COMPONENTS}
    secondary: dict[str, list[dict[str, str]]] = {key: [] for key in COMPONENTS}

    geodata = data["geodata"]
    for key in ("source_manifest", "visual_context"):
        if key in geodata:
            path = _resolve_file(files["geodata"].parent, geodata[key], repository_root)
            secondary["geodata"].append({"kind": key, "path": _relative(path, repository_root)})

    sensors = data["sensors"]
    if "source_catalog" in sensors:
        path = _resolve_file(files["sensors"].parent, sensors["source_catalog"], repository_root)
        secondary["sensors"].append({"kind": "source_catalog", "path": _relative(path, repository_root)})

    sectors = data["sectors"]
    if "policy_source" in sectors:
        path = _resolve_file(files["sectors"].parent, sectors["policy_source"], repository_root)
        secondary["sectors"].append({"kind": "policy_source", "path": _relative(path, repository_root)})

    scenarios = data["scenarios"]
    for scenario in scenarios.get("scenarios", []):
        if not isinstance(scenario, dict):
            raise ValueError("scenarios.scenarios entries must be objects")
        scenario_id = scenario.get("id", "")
        for key in ("entrypoint", "timeline", "fixture"):
            if key in scenario:
                path = _resolve_file(files["scenarios"].parent, scenario[key], repository_root)
                secondary["scenarios"].append(
                    {"kind": key, "scenario_id": str(scenario_id), "path": _relative(path, repository_root)}
                )

    compatibility: dict[str, str] = {}
    for key, reference in (manifest.get("compatibility") or {}).items():
        path = _resolve_file(manifest_file.parent, reference, repository_root)
        compatibility[str(key)] = _relative(path, repository_root)

    return {
        "schema": "bod-cuas.resolved-airport-pack",
        "version": "1.0.0",
        "manifest": {
            "id": manifest.get("id"),
            "version": manifest.get("version"),
            "display_name": manifest.get("display_name"),
            "authority_boundary": manifest.get("authority_boundary"),
            "path": _relative(manifest_file, repository_root),
        },
        "components": {
            key: {"path": _relative(files[key], repository_root), "data": data[key]}
            for key in COMPONENTS
        },
        "secondary_references": secondary,
        "compatibility": compatibility,
    }
