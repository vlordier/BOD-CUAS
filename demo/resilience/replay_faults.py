#!/usr/bin/env python3
"""Deterministic fault-injection replay for resilience testing.

This tool is deliberately independent of the golden replay and of NATS.  It
turns a small scenario fixture into a reproducible JSONL stream while making
transport and observation faults explicit in each emitted record.

Scenario format (JSON or YAML when PyYAML is installed)::

    scenario_id: sensor-conflict
    seed: 7
    events:
      - id: radar-1
        at_ms: 1000
        subject: surveillance.observation
        data: {track_id: "4660", source: radar}
    faults:
      latency_ms: 100
      loss: {ids: [rf-1]}
      duplicate: {ids: [radar-1], count: 1}
      reorder_window: 2
      stale_after_ms: 500
      clock_skew_ms: 250
      identity_mismatch: {ids: [rf-1], observed_track_id: "9999"}

Faults can also be specified on an individual event using the same keys.  The
output contains only scenario observations and transport metadata.  Authority
fields are copied byte-for-byte from input; no Core/S1 authority, delegation,
abort, acknowledgement, or execution evidence is created by this harness.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SCENARIO: dict[str, Any] = {
    "schema": "furia.cuas.resilience-scenario",
    "version": "1.0.0",
    "id": "resilience-default",
    "title": "Default deterministic resilience observation",
    "purpose": "Offline loader smoke scenario.",
    "seed": 0,
    "duration_ms": 1000,
    "actors": [{"id": "uas-default", "kind": "uas", "classification": "unknown", "state": {"position": {"x_m": 0, "y_m": 0, "z_m": 100}, "velocity": {"x_m": 1, "y_m": 0, "z_m": 0}, "uncertainty": {"x_m": 1, "y_m": 1, "z_m": 1}}}],
    "sensors": [{"id": "sensor-default", "kind": "radar", "health": "nominal", "latency_ms": 0, "observes": ["uas-default"]}],
    "faults": {},
}

AUTHORITY_KEYS = {
    "authority",
    "authority_id",
    "delegation",
    "delegation_id",
    "execution_evidence",
    "safety_hold",
    "core_authority",
    "s1_authority",
}


def _scenario_id(scenario: dict[str, Any]) -> str:
    return str(scenario.get("scenario_id", scenario.get("id", "resilience")))


class ScenarioError(ValueError):
    """Raised when a scenario fixture is malformed."""


def _load_text(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ScenarioError(
                "YAML fixture requested but PyYAML is not installed; use JSON "
                "or install the scenario tooling dependency"
            ) from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ScenarioError("scenario root must be an object")
    return value


def discover_scenario(root: Path) -> Path | None:
    """Find the first supported event-stream or actor/state DSL fixture."""
    for directory in (root / "scenarios", root / "fixtures"):
        for pattern in ("*.json", "*.yaml", "*.yml"):
            for candidate in sorted(directory.glob(pattern)):
                try:
                    value = _load_text(candidate)
                except ScenarioError:
                    continue
                if isinstance(value.get("events", value.get("timeline")), list):
                    return candidate
                if all(isinstance(value.get(key), list) for key in ("actors", "sensors", "faults")):
                    return candidate
    return None


def _expand_resilience_dsl(scenario: dict[str, Any]) -> dict[str, Any]:
    """Expand the repository's actor/sensor/fault manifest into observations.

    The manifest describes capabilities and fault windows, not authority
    commands.  This adapter therefore emits sensor/context observations only;
    the declared ``authority`` remains metadata and is never turned into an
    event or copied into a generated payload.
    """
    if "events" in scenario or "timeline" in scenario:
        return scenario
    actors = scenario.get("actors", [])
    sensors = scenario.get("sensors", [])
    faults = scenario.get("faults", [])
    if not isinstance(actors, list) or not isinstance(sensors, list) or not isinstance(faults, list):
        raise ScenarioError("scenario actors, sensors, and faults must be lists")
    duration = _as_ms(scenario.get("duration_ms", 0), "duration_ms")
    tick = _as_ms(scenario.get("tick_ms", 1000), "tick_ms")
    if tick <= 0:
        raise ScenarioError("tick_ms must be positive")
    actor_by_id = {str(actor.get("id")): actor for actor in actors if isinstance(actor, dict) and actor.get("id") is not None}
    generated: list[dict[str, Any]] = []

    for sensor in sensors:
        if not isinstance(sensor, dict) or sensor.get("id") is None:
            continue
        sensor_id = str(sensor["id"])
        observed = sensor.get("observes", [])
        if not isinstance(observed, list):
            raise ScenarioError(f"sensor {sensor_id} observes must be a list")
        for at_ms in range(0, duration + 1, tick):
            for actor_id in observed:
                actor = actor_by_id.get(str(actor_id))
                if actor is None:
                    continue
                base_latency = _as_ms(sensor.get("latency_ms", 0), f"sensor {sensor_id}.latency_ms")
                local_faults: dict[str, Any] = {"latency_ms": base_latency} if base_latency else {}
                data: dict[str, Any] = {
                    "track_id": str(actor_id),
                    "source": sensor.get("kind", "unknown"),
                    "sensor_id": sensor_id,
                    "sensor_health": sensor.get("health", "unknown"),
                }
                state = actor.get("state", {})
                if isinstance(state, dict):
                    data["state"] = copy.deepcopy(state)
                for fault in faults:
                    if not isinstance(fault, dict):
                        continue
                    start = _as_ms(fault.get("start_ms", 0), "fault.start_ms")
                    fault_duration = _as_ms(fault.get("duration_ms", duration + tick), "fault.duration_ms")
                    target = str(fault.get("target", ""))
                    active = start <= at_ms < start + fault_duration
                    target_matches = target in {sensor_id, "network", str(actor_id), "*"}
                    if not active or not target_matches:
                        continue
                    parameters = fault.get("parameters", {})
                    if not isinstance(parameters, dict):
                        raise ScenarioError(f"fault {fault.get('id', 'unknown')} parameters must be an object")
                    fault_type = str(fault.get("type", "unknown"))
                    data.setdefault("active_faults", []).append({"id": fault.get("id"), "type": fault_type})
                    if fault_type == "message_delay":
                        local_faults["latency_ms"] = base_latency + parameters.get("additional_latency_ms", 0)
                    elif fault_type == "message_loss":
                        local_faults["loss"] = parameters.get("loss_ratio", 0)
                    elif fault_type == "stale_data":
                        local_faults["stale_after_ms"] = parameters.get("freshness_limit_ms", 0)
                    elif fault_type in {"message_duplicate", "duplicate"}:
                        local_faults["duplicate"] = {"probability": parameters.get("duplicate_ratio", 0)}
                    elif fault_type == "spoofed_identity":
                        local_faults["identity_mismatch"] = {
                            "observed_track_id": parameters.get("claimed_identity", "mismatched-track")
                        }
                    elif fault_type == "disagreement":
                        data["sensor_disagreement"] = copy.deepcopy(parameters)
                        local_faults["sensor_disagreement"] = parameters
                generated.append({
                    "id": f"{sensor_id}:{actor_id}:{at_ms}",
                    "at_ms": at_ms,
                    "subject": "surveillance.observation",
                    "data": data,
                    "faults": local_faults,
                })

    # Airport/network faults without an observed actor are still useful as
    # context events, but remain non-authoritative observations.
    for fault in faults:
        if not isinstance(fault, dict):
            continue
        generated.append({
            "id": f"fault:{fault.get('id', 'unknown')}",
            "at_ms": _as_ms(fault.get("start_ms", 0), "fault.start_ms"),
            "subject": "scenario.fault",
            "data": {
                "fault_id": fault.get("id"),
                "fault_type": fault.get("type", "unknown"),
                "target": fault.get("target"),
                "parameters": copy.deepcopy(fault.get("parameters", {})),
            },
            "faults": {"fault_marker": str(fault.get("type", "unknown"))},
        })
    expanded = copy.deepcopy(scenario)
    expanded["events"] = generated
    expanded["faults"] = {}
    expanded["source_dsl"] = "furia.cuas.resilience-scenario"
    return expanded


def load_scenario(path: Path | None, root: Path | None = None) -> dict[str, Any]:
    if path is not None:
        scenario = _load_text(path)
    else:
        found = discover_scenario(root or Path(__file__).parent)
        scenario = _load_text(found) if found else copy.deepcopy(DEFAULT_SCENARIO)
    scenario = _expand_resilience_dsl(scenario)
    events = scenario.get("events", scenario.get("timeline", []))
    if not isinstance(events, list):
        raise ScenarioError("scenario.events must be a list")
    scenario["events"] = events
    if not isinstance(scenario.get("faults", {}), dict):
        raise ScenarioError("scenario.faults must be an object")
    return scenario


def _as_ms(value: Any, field: str, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    raise ScenarioError(f"{field} must be a number of milliseconds")


def _event_id(event: dict[str, Any], index: int) -> str:
    return str(event.get("id", event.get("event_id", f"event-{index + 1}")))


def _selected(rule: Any, event: dict[str, Any], index: int) -> bool:
    if rule in (None, False, 0):
        return False
    if rule is True:
        return True
    if isinstance(rule, (int, float)) and not isinstance(rule, bool):
        return float(rule) > 0
    if isinstance(rule, list):
        return _event_id(event, index) in {str(item) for item in rule}
    if isinstance(rule, dict):
        ids = rule.get("ids", rule.get("event_ids"))
        subjects = rule.get("subjects")
        if ids is not None and _event_id(event, index) not in {str(item) for item in ids}:
            return False
        if subjects is not None and event.get("subject") not in set(subjects):
            return False
        return bool(ids is not None or subjects is not None or rule.get("enabled", True))
    return False


def _stable_fraction(seed: int, *parts: Any) -> float:
    material = "|".join([str(seed), *(str(part) for part in parts)]).encode()
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def _probability(rule: Any, event: dict[str, Any], index: int, seed: int) -> bool:
    if isinstance(rule, dict):
        probability = rule.get("probability", rule.get("rate", 0))
        if _selected(rule, event, index) is False and ("ids" in rule or "subjects" in rule):
            return False
    else:
        probability = rule
    try:
        probability = float(probability)
    except (TypeError, ValueError) as exc:
        raise ScenarioError("fault probability must be numeric") from exc
    if not 0 <= probability <= 1:
        raise ScenarioError("fault probability must be between 0 and 1")
    return _stable_fraction(seed, _event_id(event, index), "probability") < probability


def _fault_for(event: dict[str, Any], name: str, global_faults: dict[str, Any]) -> Any:
    local = event.get("faults", {})
    if isinstance(local, dict) and name in local:
        return local[name]
    return global_faults.get(name)


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("data", event.get("payload", {}))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ScenarioError(f"event {_event_id(event, 0)} data must be an object")
    return copy.deepcopy(value)


def _apply_identity_mismatch(data: dict[str, Any], rule: Any) -> bool:
    if not rule:
        return False
    if isinstance(rule, dict):
        replacement = rule.get("observed_track_id", rule.get("track_id", "mismatched-track"))
        source_field = rule.get("source_field", "source_track_id")
        track_field = rule.get("track_field", "track_id")
    else:
        replacement, source_field, track_field = "mismatched-track", "source_track_id", "track_id"
    original = data.get(track_field)
    if original is None:
        return False
    data[source_field] = original
    data[track_field] = replacement
    data["identity_mismatch"] = True
    return True


def _authority_snapshot(event: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Return only authority supplied by the fixture, without constructing it."""
    source: dict[str, Any] = {}
    for key in AUTHORITY_KEYS:
        if key in event:
            source[key] = copy.deepcopy(event[key])
        elif key in data:
            source[key] = copy.deepcopy(data[key])
    return source


def replay(scenario: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed = int(scenario.get("seed", 0))
    global_faults = scenario.get("faults", {})
    prepared: list[dict[str, Any]] = []
    dropped = 0
    duplicate_count = 0
    faults_seen: set[str] = set()

    for index, source in enumerate(scenario["events"]):
        if not isinstance(source, dict):
            raise ScenarioError(f"event {index + 1} must be an object")
        event = copy.deepcopy(source)
        event_id = _event_id(event, index)
        data = _payload(event)
        faults_applied: list[str] = []

        marker = _fault_for(event, "fault_marker", global_faults)
        if marker:
            faults_applied.append(str(marker))
            faults_seen.add(str(marker))

        if _fault_for(event, "sensor_disagreement", global_faults) is not None:
            faults_applied.append("sensor_disagreement")
            faults_seen.add("sensor_disagreement")

        loss_rule = _fault_for(event, "loss", global_faults)
        probability_only = isinstance(loss_rule, dict) and not {"ids", "event_ids", "subjects"}.intersection(loss_rule)
        probability_rule = isinstance(loss_rule, (int, float)) and not isinstance(loss_rule, bool)
        should_drop = False if probability_only or probability_rule else _selected(loss_rule, event, index)
        if isinstance(loss_rule, dict) and not probability_only and should_drop and ("probability" in loss_rule or "rate" in loss_rule):
            should_drop = _probability(loss_rule, event, index, seed)
        if not should_drop and isinstance(loss_rule, (int, float, dict)) and not isinstance(loss_rule, bool):
            # A rule with explicit ids/subjects selects a population; a rule
            # with only probability/rate selects deterministically by seed.
            if isinstance(loss_rule, dict) and ("ids" in loss_rule or "subjects" in loss_rule):
                should_drop = _probability(loss_rule, event, index, seed)
            elif isinstance(loss_rule, (int, float)) or isinstance(loss_rule, dict):
                should_drop = _probability(loss_rule, event, index, seed)
        if should_drop:
            dropped += 1
            faults_seen.add("loss")
            continue

        base_ms = _as_ms(event.get("at_ms", event.get("timestamp_ms", event.get("at", 0))), "event time")
        latency_rule = _fault_for(event, "latency_ms", global_faults)
        if isinstance(latency_rule, dict):
            latency = _as_ms(latency_rule.get("value", latency_rule.get("ms", 0)), "latency_ms")
            if not _selected(latency_rule, event, index):
                latency = 0
        else:
            latency = _as_ms(latency_rule, "latency_ms") if latency_rule is not None else 0
        if latency:
            faults_applied.append("latency")
            faults_seen.add("latency")

        skew_rule = _fault_for(event, "clock_skew_ms", global_faults)
        skew = _as_ms(skew_rule, "clock_skew_ms") if skew_rule is not None else 0
        if skew:
            faults_applied.append("clock_skew")
            faults_seen.add("clock_skew")

        stale_rule = _fault_for(event, "stale_data", global_faults)
        if stale_rule is None:
            stale_rule = _fault_for(event, "stale_after_ms", global_faults)
        stale_after = None
        if stale_rule is not None:
            stale_after = _as_ms(stale_rule.get("after_ms", stale_rule) if isinstance(stale_rule, dict) else stale_rule, "stale_after_ms")
            if stale_after < 0:
                raise ScenarioError("stale_after_ms cannot be negative")
            data["stale"] = True
            data["freshness_ms"] = stale_after
            faults_applied.append("stale_data")
            faults_seen.add("stale_data")

        mismatch_rule = _fault_for(event, "identity_mismatch", global_faults)
        mismatch_applied = False
        if isinstance(mismatch_rule, dict) and not _selected(mismatch_rule, event, index):
            mismatch_rule = None
        if mismatch_rule:
            mismatch_applied = _apply_identity_mismatch(data, mismatch_rule)
            if mismatch_applied:
                faults_applied.append("identity_mismatch")
                faults_seen.add("identity_mismatch")

        record = {
            "scenario_id": _scenario_id(scenario),
            "event_id": event_id,
            "subject": event.get("subject", "scenario.observation"),
            "scheduled_at_ms": base_ms + latency,
            "observed_at_ms": base_ms + latency + skew,
            "data": data,
            "faults_applied": faults_applied,
            "authority_observed": _authority_snapshot(event, data),
            "source_index": index,
        }
        prepared.append(record)

        duplicate_rule = _fault_for(event, "duplicate", global_faults)
        count = 0
        if isinstance(duplicate_rule, dict):
            has_selector = bool({"ids", "event_ids", "subjects"}.intersection(duplicate_rule))
            if ("probability" in duplicate_rule or "rate" in duplicate_rule) and not has_selector:
                count = 1 if _probability(duplicate_rule, event, index, seed) else 0
            elif _selected(duplicate_rule, event, index):
                count = int(duplicate_rule.get("count", 1))
        elif duplicate_rule is True:
            count = 1
        if count < 0:
            raise ScenarioError("duplicate count cannot be negative")
        for duplicate_index in range(count):
            duplicate = copy.deepcopy(record)
            duplicate["event_id"] = f"{event_id}#duplicate-{duplicate_index + 1}"
            duplicate["faults_applied"] = [*record["faults_applied"], "duplication"]
            duplicate["duplicate_of"] = event_id
            prepared.append(duplicate)
            duplicate_count += 1
            faults_seen.add("duplication")

    prepared.sort(key=lambda item: (item["scheduled_at_ms"], item["source_index"], item["event_id"]))
    reorder_rule = global_faults.get("reorder_window", 0)
    window = int(reorder_rule.get("size", 0) if isinstance(reorder_rule, dict) else reorder_rule or 0)
    if window < 0:
        raise ScenarioError("reorder_window cannot be negative")
    if window > 1:
        reordered: list[dict[str, Any]] = []
        for start in range(0, len(prepared), window):
            chunk = prepared[start : start + window]
            reordered.extend(reversed(chunk))
        prepared = reordered
        for record in prepared:
            if "reordering" not in record["faults_applied"]:
                record["faults_applied"].append("reordering")
                faults_seen.add("reordering")

    for sequence, record in enumerate(prepared, 1):
        record["sequence"] = sequence

    summary = {
        "scenario_id": _scenario_id(scenario),
        "seed": seed,
        "input_events": len(scenario["events"]),
        "emitted_events": len(prepared),
        "dropped_events": dropped,
        "duplicate_events": duplicate_count,
        "faults": sorted(faults_seen),
        "authority_records_observed": sum(bool(record["authority_observed"]) for record in prepared),
        "authority_records_created": 0,
        "authority_declared_in_fixture": "authority" in scenario,
        "source_dsl": scenario.get("source_dsl", "event-stream"),
    }
    return prepared, summary


def _write_jsonl(records: Iterable[dict[str, Any]], output: Path | None) -> None:
    stream = output.open("w", encoding="utf-8") if output else sys.stdout
    try:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    finally:
        if output:
            stream.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, help="JSON/YAML scenario fixture")
    parser.add_argument("--output", type=Path, help="JSONL output path; defaults to stdout")
    parser.add_argument("--summary-output", type=Path, help="optional JSON summary path")
    args = parser.parse_args(argv)
    try:
        records, summary = replay(load_scenario(args.scenario))
        _write_jsonl(records, args.output)
        summary_text = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        if args.summary_output:
            args.summary_output.write_text(summary_text + "\n", encoding="utf-8")
        print(f"replay: {summary['scenario_id']} emitted={summary['emitted_events']} dropped={summary['dropped_events']} faults={','.join(summary['faults']) or 'none'}", file=sys.stderr)
        return 0
    except (OSError, ScenarioError, json.JSONDecodeError) as exc:
        print(f"replay_faults: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
