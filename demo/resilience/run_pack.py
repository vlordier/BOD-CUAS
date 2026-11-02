#!/usr/bin/env python3
"""Execute every resilience fixture and assert its scenario-specific invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from loader import load_scenario as validate_scenario
from replay_faults import load_scenario as load_replay_scenario, replay

ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios"


def assert_scenario(scenario_id: str, records: list[dict], summary: dict) -> None:
    faults = set(summary["faults"])
    if summary["authority_records_created"] != 0:
        raise AssertionError(f"{scenario_id}: replay created authority")
    if not records:
        raise AssertionError(f"{scenario_id}: replay emitted no records")
    if scenario_id == "sensor-conflict":
        if not {"sensor_disagreement", "identity_mismatch"}.issubset(faults):
            raise AssertionError(f"{scenario_id}: disagreement and identity faults are required")
    elif scenario_id == "stale-track":
        if "stale_data" not in faults or summary["dropped_events"] == 0:
            raise AssertionError(f"{scenario_id}: stale and loss faults were not exercised")
    elif scenario_id == "authority-expiry":
        if "authority_expiry" not in faults or "message_delay" not in faults:
            raise AssertionError(f"{scenario_id}: expiry and acknowledgement delay are required")
    elif scenario_id == "multi-threat-saturation":
        tracks = {record["data"].get("track_id") for record in records}
        if len(tracks - {None}) < 5 or summary["duplicate_events"] == 0:
            raise AssertionError(f"{scenario_id}: saturation must include five tracks and duplication")
    elif scenario_id == "runway-state-change":
        if "runway_state_change" not in faults or "message_delay" not in faults:
            raise AssertionError(f"{scenario_id}: runway change and delayed acknowledgement are required")


def run(output_dir: Path | None = None) -> dict:
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in sorted(SCENARIOS.glob("*.json")):
        validate_scenario(path)
        scenario = load_replay_scenario(path)
        records, summary = replay(scenario)
        assert_scenario(summary["scenario_id"], records, summary)
        summaries.append(summary)
        if output_dir:
            output_dir.joinpath(f"{summary['scenario_id']}.jsonl").write_text(
                "".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8"
            )
            output_dir.joinpath(f"{summary['scenario_id']}.summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    return {"schema": "bod-cuas.resilience-run", "version": "1.0.0", "scenarios": summaries}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on any scenario invariant violation")
    parser.add_argument("--output-dir", type=Path, help="write JSONL and summaries to this directory")
    args = parser.parse_args(argv)
    try:
        report = run(args.output_dir)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"resilience run failed: {exc}", file=sys.stderr)
        return 1 if args.check else 2


if __name__ == "__main__":
    raise SystemExit(main())
