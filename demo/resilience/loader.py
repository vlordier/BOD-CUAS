#!/usr/bin/env python3
"""Load and validate the BOD-CUAS resilience scenario DSL.

The loader is intentionally offline and side-effect free. A scenario is a
versioned JSON document with actors, sensors, faults, authority, and expected
outcomes. The deterministic seed belongs to the scenario and is included in
the canonical digest used by test runners and future simulators.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

CURRENT_SCHEMA_VERSION = "1.0.0"
SCENARIO_DIR = Path(__file__).parent / "scenarios"


class ScenarioError(ValueError):
    """Raised when a resilience scenario is malformed or unsafe to load."""


def _require(value: Any, path: str, expected: str) -> Any:
    if value is None:
        raise ScenarioError(f"{path} is required ({expected})")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{path} must be a non-empty string")
    return value


def _number(value: Any, path: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{path} must be a number")
    if integer and not isinstance(value, int):
        raise ScenarioError(f"{path} must be an integer")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScenarioError(f"{path} must be an array")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScenarioError(f"{path} must be an object")
    return value


def _unique_ids(items: Iterable[dict[str, Any]], path: str) -> set[str]:
    result: set[str] = set()
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        identifier = _string(item.get("id"), f"{item_path}.id")
        if identifier in result:
            raise ScenarioError(f"duplicate id {identifier!r} in {path}")
        result.add(identifier)
    return result


def _validate_actor(actor: dict[str, Any], index: int) -> None:
    path = f"actors[{index}]"
    _string(actor.get("id"), f"{path}.id")
    _string(actor.get("kind"), f"{path}.kind")
    _string(actor.get("classification"), f"{path}.classification")
    state = _object(_require(actor.get("state"), f"{path}.state", "object"), f"{path}.state")
    for field in ("position", "velocity", "uncertainty"):
        vector = _object(_require(state.get(field), f"{path}.state.{field}", "object"), f"{path}.state.{field}")
        for component in ("x_m", "y_m", "z_m"):
            _number(_require(vector.get(component), f"{path}.state.{field}.{component}", "number"), f"{path}.state.{field}.{component}")


def _validate_sensor(sensor: dict[str, Any], index: int, actor_ids: set[str]) -> None:
    path = f"sensors[{index}]"
    _string(sensor.get("id"), f"{path}.id")
    _string(sensor.get("kind"), f"{path}.kind")
    _string(sensor.get("health"), f"{path}.health")
    _number(_require(sensor.get("latency_ms"), f"{path}.latency_ms", "integer"), f"{path}.latency_ms", integer=True)
    if sensor["latency_ms"] < 0:
        raise ScenarioError(f"{path}.latency_ms cannot be negative")
    observed = _list(_require(sensor.get("observes"), f"{path}.observes", "array"), f"{path}.observes")
    for target in observed:
        if target not in actor_ids:
            raise ScenarioError(f"{path}.observes references unknown actor {target!r}")


def _validate_fault(fault: dict[str, Any], index: int, actor_ids: set[str], sensor_ids: set[str]) -> None:
    path = f"faults[{index}]"
    _string(fault.get("id"), f"{path}.id")
    fault_type = _string(fault.get("type"), f"{path}.type")
    target = _string(fault.get("target"), f"{path}.target")
    if target not in actor_ids and target not in sensor_ids and target != "network":
        raise ScenarioError(f"{path}.target references unknown actor/sensor {target!r}")
    _number(_require(fault.get("start_ms"), f"{path}.start_ms", "integer"), f"{path}.start_ms", integer=True)
    _number(_require(fault.get("duration_ms"), f"{path}.duration_ms", "integer"), f"{path}.duration_ms", integer=True)
    if fault["start_ms"] < 0 or fault["duration_ms"] <= 0:
        raise ScenarioError(f"{path} must have non-negative start and positive duration")
    parameters = _object(_require(fault.get("parameters"), f"{path}.parameters", "object"), f"{path}.parameters")
    if fault_type in {"stale_data", "message_delay", "message_loss", "message_duplicate", "out_of_order"} and not parameters:
        raise ScenarioError(f"{path}.parameters must describe the fault")


def _validate_authority(authority: dict[str, Any], actor_ids: set[str]) -> None:
    _string(authority.get("id"), "authority.id")
    _string(authority.get("source"), "authority.source")
    _string(authority.get("status"), "authority.status")
    scope = _object(_require(authority.get("scope"), "authority.scope", "object"), "authority.scope")
    target = _string(scope.get("target_actor"), "authority.scope.target_actor")
    if target not in actor_ids:
        raise ScenarioError(f"authority.scope.target_actor references unknown actor {target!r}")
    _number(_require(authority.get("valid_from_ms"), "authority.valid_from_ms", "integer"), "authority.valid_from_ms", integer=True)
    _number(_require(authority.get("valid_until_ms"), "authority.valid_until_ms", "integer"), "authority.valid_until_ms", integer=True)
    if authority["valid_until_ms"] <= authority["valid_from_ms"]:
        raise ScenarioError("authority.valid_until_ms must be after valid_from_ms")
    constraints = _list(_require(authority.get("constraints"), "authority.constraints", "array"), "authority.constraints")
    if not all(isinstance(item, str) and item for item in constraints):
        raise ScenarioError("authority.constraints must contain non-empty strings")


def validate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a scenario without mutating it."""
    _object(scenario, "scenario")
    _string(scenario.get("schema"), "schema")
    if scenario["schema"] != "furia.cuas.resilience-scenario":
        raise ScenarioError(f"unsupported schema {scenario['schema']!r}")
    _string(scenario.get("version"), "version")
    if scenario["version"] != CURRENT_SCHEMA_VERSION:
        raise ScenarioError(f"unsupported version {scenario['version']!r}")
    _string(scenario.get("id"), "id")
    _string(scenario.get("title"), "title")
    _string(scenario.get("purpose"), "purpose")
    seed = _number(_require(scenario.get("seed"), "seed", "integer"), "seed", integer=True)
    if seed < 0:
        raise ScenarioError("seed must be non-negative")
    duration = _number(_require(scenario.get("duration_ms"), "duration_ms", "integer"), "duration_ms", integer=True)
    if duration <= 0:
        raise ScenarioError("duration_ms must be positive")

    actors = _list(_require(scenario.get("actors"), "actors", "array"), "actors")
    actor_ids = _unique_ids(actors, "actors")
    for index, actor in enumerate(actors):
        _validate_actor(_object(actor, f"actors[{index}]"), index)

    sensors = _list(_require(scenario.get("sensors"), "sensors", "array"), "sensors")
    sensor_ids = _unique_ids(sensors, "sensors")
    for index, sensor in enumerate(sensors):
        _validate_sensor(_object(sensor, f"sensors[{index}]"), index, actor_ids)

    faults = _list(_require(scenario.get("faults"), "faults", "array"), "faults")
    _unique_ids(faults, "faults")
    for index, fault in enumerate(faults):
        _validate_fault(_object(fault, f"faults[{index}]"), index, actor_ids, sensor_ids)

    authority = _object(_require(scenario.get("authority"), "authority", "object"), "authority")
    _validate_authority(authority, actor_ids)

    expected = _object(_require(scenario.get("expected_outcome"), "expected_outcome", "object"), "expected_outcome")
    _string(expected.get("final_state"), "expected_outcome.final_state")
    assertions = _list(_require(expected.get("assertions"), "expected_outcome.assertions", "array"), "expected_outcome.assertions")
    if not assertions or not all(isinstance(item, str) and item for item in assertions):
        raise ScenarioError("expected_outcome.assertions must contain at least one non-empty string")
    return scenario


def load_scenario(path: str | Path) -> dict[str, Any]:
    """Read, parse, and validate one JSON scenario."""
    scenario_path = Path(path)
    try:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScenarioError(f"cannot read {scenario_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"invalid JSON in {scenario_path}: {exc}") from exc
    return validate_scenario(scenario)


def load_all(directory: str | Path = SCENARIO_DIR) -> list[dict[str, Any]]:
    """Load all scenario JSON files in stable filename order."""
    paths = sorted(Path(directory).glob("*.json"))
    scenarios = [load_scenario(path) for path in paths]
    ids = [scenario["id"] for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ScenarioError("scenario ids must be unique")
    return scenarios


def scenario_digest(scenario: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest of a validated scenario."""
    validate_scenario(scenario)
    canonical = json.dumps(scenario, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
