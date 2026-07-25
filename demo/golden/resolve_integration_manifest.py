#!/usr/bin/env python3
"""Validate and resolve the Bordeaux golden-demo integration manifest.

Development uses named refs. A release gate can require immutable SHA pins
without changing the local sibling-checkout workflow.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MANIFEST_PATH = Path(__file__).with_name("integration-manifest.json")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_IDS = {"furia_core", "furia_ui", "furia_c2", "s1"}


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != "furia.golden.integration-manifest":
        raise ValueError("unsupported integration manifest schema")
    if manifest.get("version") != "1.0.0":
        raise ValueError("unsupported integration manifest version")
    repositories = manifest.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("repositories must be a list")
    ids = [repository.get("id") for repository in repositories]
    if set(ids) != REQUIRED_IDS or len(ids) != len(set(ids)):
        raise ValueError("manifest must contain each required repository exactly once")
    for repository in repositories:
        if not all(isinstance(repository.get(field), str) and repository[field].strip()
                   for field in ("id", "path", "repository", "development_ref")):
            raise ValueError(f"invalid repository entry: {repository.get('id', '<unknown>')}")
        pin = repository.get("pinned_ref")
        if pin is not None and (not isinstance(pin, str) or not SHA_PATTERN.fullmatch(pin)):
            raise ValueError(f"pinned_ref for {repository['id']} must be a 40-character lowercase Git SHA")
    return manifest


def resolved_repositories(manifest: dict, *, require_pins: bool = False) -> tuple[dict[str, str], bool]:
    refs: dict[str, str] = {}
    all_pinned = True
    for repository in manifest["repositories"]:
        pin = repository.get("pinned_ref")
        if pin is None:
            all_pinned = False
            refs[repository["id"]] = repository["development_ref"]
        else:
            refs[repository["id"]] = pin
    if require_pins and not all_pinned:
        raise ValueError("release gate requires pinned_ref for every integration repository")
    return refs, all_pinned


def write_github_output(path: Path, refs: dict[str, str], all_pinned: bool) -> None:
    with path.open("a") as output:
        for repository_id, ref in sorted(refs.items()):
            output.write(f"{repository_id}_ref={ref}\n")
        output.write(f"all_pinned={'true' if all_pinned else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--require-pins", action="store_true")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        refs, all_pinned = resolved_repositories(manifest, require_pins=args.require_pins)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"integration manifest: FAIL: {error}", file=sys.stderr)
        return 1
    for repository_id, ref in sorted(refs.items()):
        source = "pinned" if SHA_PATTERN.fullmatch(ref) else "development"
        print(f"integration manifest: {repository_id}={ref} ({source})")
    print(f"integration manifest: all_pinned={'true' if all_pinned else 'false'}")
    if args.github_output:
        write_github_output(args.github_output, refs, all_pinned)
    return 0


if __name__ == "__main__":
    sys.exit(main())
