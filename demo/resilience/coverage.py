#!/usr/bin/env python3
"""Coverage manifest and report for the BOD-CUAS simulations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SAFETY_STATES = (
    "surveillance", "assessment", "authorization_pending", "bounded_execution",
    "lost_link_continuation", "safety_inhibition", "safe_hold_confirmed", "recovery",
)

SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "bod-cuas-golden",
        "title": "Bordeaux deterministic authority and safety-abort replay",
        "source": "demo/golden/replay.py",
        "inputs": ["non_cooperative_uas_track", "rf_acoustic_fusion", "operator_authorization", "bounded_non_effect_delegation", "lost_link_then_recovery", "civil_aircraft_conflict", "core_safety_abort", "contract_correlated_s1_safe_hold"],
        "safety_states": list(SAFETY_STATES),
        "expected_outcomes": [
            "Core delegates only after named operator authorization.",
            "Lost-link continuation preserves the existing bounded contract.",
            "Civilian conflict causes a Core-issued safety abort.",
            "S1 emits correlated aborted/safety_hold evidence.",
            "All acceptance verifiers pass and the run exits non-zero on failure.",
        ],
        "authority_boundary": {
            "owner": "furia-core",
            "allowed": ["bounded_non_effect_track_and_shadow"],
            "prohibited": ["autonomous_detect_to_defeat", "effect_authority", "c2_generated_authority"],
            "evidence_required": "delegation_correlation_id_and_core_abort_policy",
        },
        "verifiers": [
            {"id": "verify", "path": "demo/golden/verify.py", "proves": "causal_abort_and_safe_hold_correlation"},
            {"id": "verify-origin", "path": "demo/golden/verify_origin.py", "proves": "delegation_origin_and_identity"},
            {"id": "verify-comm-denied", "path": "demo/golden/verify_comm_denied.py", "proves": "lost_link_continuation_and_recovery"},
            {"id": "fixture-tests", "path": "demo/golden/test_abort_correlation.py", "proves": "contract_matching_helpers"},
        ],
        "verification_status": "verified",
        "verification_basis": "Fresh live replay passed all three golden verifiers; fixture tests pass.",
    },
    {
        "id": "live-context-display-only",
        "title": "Live-context provenance and degraded-source display simulation",
        "source": "demo/live-context/context_simulator.py",
        "inputs": ["weather_context", "airport_operations_context", "uspace_context", "eo_ir_klv_metadata"],
        "safety_states": ["surveillance", "assessment"],
        "expected_outcomes": ["Context feeds expose provenance, freshness, and limitations.", "Degraded or disconnected sources remain visibly non-authoritative.", "No context feed can create a command, authorization, or safety decision."],
        "authority_boundary": {
            "owner": "none_context_only",
            "allowed": ["render_context", "report_provenance", "report_freshness"],
            "prohibited": ["issue_command", "create_authority", "replace_atc_or_aodb"],
            "evidence_required": "source_catalog_state_and_authority_fields",
        },
        "verifiers": [
            {"id": "source-catalog-tests", "path": "demo/live-context/test_source_catalog.py", "proves": "safe_source_state_and_boundary"},
            {"id": "context-bridge-tests", "path": "demo/live-context/test_context_bridge.py", "proves": "context_only_bridge_behavior"},
        ],
        "verification_status": "verified",
        "verification_basis": "Source-catalog and context-bridge tests validate context-only boundaries.",
    },
    {
        "id": "sensor-conflict", "title": "Conflicting sensor evidence", "source": None,
        "inputs": ["radar_track", "rf_bearing_disagreement", "acoustic_disagreement", "low_confidence_eo_ir", "authorized_remote_id_claim"],
        "safety_states": ["surveillance", "assessment", "safety_inhibition"], "expected_outcomes": ["Conflicting sources remain distinguishable and do not silently increase authority."], "authority_boundary": {"owner": "fixture_only", "allowed": ["validate_and_render_scenario"], "prohibited": ["issue_command", "autonomous_defeat"], "evidence_required": "loader_validation_and_scenario_digest"}, "verifiers": [{"id": "loader-tests", "path": "demo/resilience/test_loader.py", "proves": "schema_and_reference_validation"}, {"id": "resilience-pack", "path": "demo/resilience/run_pack.py", "proves": "offline_sensor_conflict_fault_invariants"}], "verification_status": "partial", "verification_basis": "Strict loader and deterministic offline replay invariants pass; no live sensor simulator is implied.",
    },
    {
        "id": "stale-track", "title": "Stale track and freshness degradation", "source": None,
        "inputs": ["track_update_timeout", "expired_freshness", "degraded_sensor_health"],
        "safety_states": ["surveillance", "assessment", "safety_inhibition"], "expected_outcomes": ["Expired freshness degrades the track and prevents stale data from authorizing action."], "authority_boundary": {"owner": "fixture_only", "allowed": ["validate_and_render_scenario"], "prohibited": ["issue_command", "extend_authority"], "evidence_required": "loader_validation_and_scenario_digest"}, "verifiers": [{"id": "loader-tests", "path": "demo/resilience/test_loader.py", "proves": "freshness_fault_fixture_validation"}, {"id": "resilience-pack", "path": "demo/resilience/run_pack.py", "proves": "offline_stale_and_loss_invariants"}], "verification_status": "partial", "verification_basis": "Strict loader and deterministic offline replay invariants pass; no live sensor simulator is implied.",
    },
    {
        "id": "authority-expiry", "title": "Delegation expiry before execution acknowledgement", "source": None,
        "inputs": ["short_validity_delegation", "delayed_execution_acknowledgement", "time_to_entry_decrease"],
        "safety_states": ["authorization_pending", "bounded_execution", "safety_inhibition", "safe_hold_confirmed"], "expected_outcomes": ["Expired delegation cannot be executed or extended and produces correlated safe-hold evidence."], "authority_boundary": {"owner": "fixture_only", "allowed": ["validate_and_render_scenario"], "prohibited": ["issue_command", "extend_authority"], "evidence_required": "loader_validation_and_scenario_digest"}, "verifiers": [{"id": "loader-tests", "path": "demo/resilience/test_loader.py", "proves": "authority_window_validation"}, {"id": "resilience-pack", "path": "demo/resilience/run_pack.py", "proves": "offline_expiry_and_no_authority_creation"}], "verification_status": "partial", "verification_basis": "Strict loader and deterministic offline replay invariants pass; no live authority simulator is implied.",
    },
    {
        "id": "multi-threat-saturation", "title": "Multiple simultaneous threats and limited interceptor capacity", "source": None,
        "inputs": ["five_or_more_uas_tracks", "limited_interceptor_assets", "competing_protected_volumes"],
        "safety_states": ["surveillance", "assessment", "authorization_pending", "safety_inhibition"], "expected_outcomes": ["Threat prioritization is deterministic, capacity limits are visible, and unassigned tracks retain surveillance-only posture."], "authority_boundary": {"owner": "fixture_only", "allowed": ["validate_and_render_scenario"], "prohibited": ["issue_command", "double_book_resources"], "evidence_required": "loader_validation_and_scenario_digest"}, "verifiers": [{"id": "loader-tests", "path": "demo/resilience/test_loader.py", "proves": "actor_and_sensor_reference_validation"}, {"id": "resilience-pack", "path": "demo/resilience/run_pack.py", "proves": "offline_saturation_and_deduplication_invariants"}], "verification_status": "partial", "verification_basis": "Strict loader and deterministic offline replay invariants pass; no live resource allocator is implied.",
    },
    {
        "id": "runway-state-change", "title": "Runway or ATC operational state changes during response", "source": None,
        "inputs": ["active_runway_change", "delayed_atc_acknowledgement", "approach_sector_conflict"],
        "safety_states": ["assessment", "bounded_execution", "safety_inhibition", "safe_hold_confirmed"], "expected_outcomes": ["A runway or ATC state change re-evaluates risk and inhibits execution until the new context is acknowledged."], "authority_boundary": {"owner": "fixture_only", "allowed": ["validate_and_render_scenario"], "prohibited": ["issue_atc_clearance", "issue_command"], "evidence_required": "loader_validation_and_scenario_digest"}, "verifiers": [{"id": "loader-tests", "path": "demo/resilience/test_loader.py", "proves": "runway_fault_fixture_validation"}, {"id": "resilience-pack", "path": "demo/resilience/run_pack.py", "proves": "offline_runway_change_and_ack_delay_invariants"}], "verification_status": "partial", "verification_basis": "Strict loader and deterministic offline replay invariants pass; no live ATC integration is implied.",
    },
)


def validate_manifest(scenarios: tuple[dict[str, Any], ...] = SCENARIOS) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for scenario in scenarios:
        scenario_id = scenario.get("id")
        prefix = scenario_id or "<missing id>"
        if not scenario_id or scenario_id in seen:
            errors.append(f"{prefix}: scenario id must be present and unique")
        seen.add(scenario_id)
        for field in ("inputs", "safety_states"):
            if not isinstance(scenario.get(field), list) or not scenario[field]:
                errors.append(f"{prefix}: {field} must be a non-empty list")
        invalid = set(scenario.get("safety_states", ())) - set(SAFETY_STATES)
        if invalid:
            errors.append(f"{prefix}: unknown safety states: {', '.join(sorted(invalid))}")
        if not isinstance(scenario.get("expected_outcomes"), list) or not scenario["expected_outcomes"]:
            errors.append(f"{prefix}: expected_outcomes is required")
        boundary = scenario.get("authority_boundary")
        if not isinstance(boundary, dict) or not boundary.get("owner"):
            errors.append(f"{prefix}: authority_boundary.owner is required")
        elif not boundary.get("allowed") or not boundary.get("prohibited") or not boundary.get("evidence_required"):
            errors.append(f"{prefix}: authority boundary must declare allowed, prohibited, and evidence_required")
        if scenario.get("verification_status") not in {"verified", "partial", "not_implemented"}:
            errors.append(f"{prefix}: invalid verification_status")
        if scenario.get("verification_status") == "verified" and not scenario.get("verifiers"):
            errors.append(f"{prefix}: verified scenario must name at least one verifier")
        if scenario.get("verification_status") in {"verified", "partial"} and not isinstance(scenario.get("verifiers"), list):
            errors.append(f"{prefix}: implemented scenario must declare verifiers")
    return errors


def build_report() -> dict[str, Any]:
    errors = validate_manifest()
    statuses = ("verified", "partial", "not_implemented")
    counts = {status: sum(s["verification_status"] == status for s in SCENARIOS) for status in statuses}
    exercised = sorted({state for s in SCENARIOS if s["verification_status"] == "verified" for state in s["safety_states"]})
    return {"schema": "bod-cuas.scenario-coverage", "version": "1.0.0", "scope": "BOD-CUAS simulation and verifier coverage; no runtime behavior", "manifest_valid": not errors, "manifest_errors": errors, "summary": {"scenario_count": len(SCENARIOS), **counts, "known_safety_states": list(SAFETY_STATES), "verified_safety_states": exercised, "unverified_safety_states": sorted(set(SAFETY_STATES) - set(exercised))}, "scenarios": list(SCENARIOS)}


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# BOD-CUAS scenario coverage", "", f"Manifest valid: **{'yes' if report['manifest_valid'] else 'no'}**", "", f"Scenarios: {summary['scenario_count']} · verified: {summary['verified']} · partial: {summary['partial']} · not_implemented: {summary['not_implemented']}", "", "## Safety-state coverage", "", "| State | Verified by at least one scenario |", "|---|---|"]
    lines.extend(f"| `{state}` | {'yes' if state in summary['verified_safety_states'] else 'no'} |" for state in summary["known_safety_states"])
    lines.extend(["", "## Scenarios", "", "| ID | Status | States | Verifiers |", "|---|---|---|---|"])
    for scenario in report["scenarios"]:
        verifiers = ", ".join(v["id"] for v in scenario["verifiers"]) or "—"
        lines.append(f"| `{scenario['id']}` | `{scenario['verification_status']}` | {', '.join(scenario['safety_states'])} | {verifiers} |")
    lines.extend(["", "## Safety boundary rule", "", "Every scenario must declare expected outcomes and an authority boundary. The checker fails closed when either is absent.", ""])
    if report["manifest_errors"]:
        lines.extend(["## Manifest errors", "", *[f"- {error}" for error in report["manifest_errors"]], ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--check", action="store_true", help="fail if the manifest is structurally invalid")
    parser.add_argument("--output", type=Path, help="write report to a file instead of stdout")
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n" if args.format == "json" else markdown_report(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 1 if args.check and report["manifest_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
