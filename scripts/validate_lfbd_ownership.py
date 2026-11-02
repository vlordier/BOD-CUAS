#!/usr/bin/env python3
"""Validate the explicit ownership inventory for LFBD demo artefacts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts/lfbd-demo-ownership.json"


def expand(pattern: str) -> list[Path]:
    if pattern.endswith("/**"):
        candidates = [path for path in ROOT.joinpath(pattern[:-3]).rglob("*") if path.is_file()]
    else:
        candidates = [path for path in ROOT.glob(pattern) if path.is_file()]
    return sorted(candidates)


def main() -> int:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"LFBD ownership manifest: FAIL ({error})")
        return 1

    errors: list[str] = []
    if manifest.get("owner_repository") != "BOD-CUAS":
        errors.append("owner_repository must be BOD-CUAS")
    if manifest.get("airport_icao") != "LFBD":
        errors.append("airport_icao must be LFBD")

    owned = manifest.get("owned", {})
    for category, patterns in owned.items():
        if category == "stories" and not patterns:
            continue
        for pattern in patterns:
            matches = expand(pattern)
            if not matches:
                errors.append(f"{category}: no files match {pattern!r}")

    for pattern in owned.get("stories", []):
        for path in expand(pattern):
            if "lfbd" not in path.as_posix().lower():
                errors.append(f"stories must be LFBD-specific: {path.relative_to(ROOT)}")

    # Keep the manifest itself authoritative and prevent accidental ownership
    # claims outside this repository through relative traversal.
    for section in ("owned", "not_owned_here"):
        values = manifest.get(section, {})
        for category, patterns in values.items():
            for pattern in patterns:
                if ".." in Path(pattern).parts:
                    errors.append(f"{section}.{category} escapes repository: {pattern!r}")

    # Every airport pack component must resolve inside BOD-CUAS.
    pack = ROOT / "demo/golden/airport-packs/lfbd/manifest.json"
    try:
        pack_manifest = json.loads(pack.read_text(encoding="utf-8"))
        for name, relative in pack_manifest.get("components", {}).items():
            target = (pack.parent / relative).resolve()
            if ROOT not in target.parents:
                errors.append(f"airport-pack component escapes repository: {name} -> {relative}")
            elif not target.is_file():
                errors.append(f"airport-pack component missing: {name} -> {relative}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"airport-pack manifest unreadable: {error}")

    if errors:
        print("LFBD ownership validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("LFBD ownership validation: PASS")
    for category, patterns in owned.items():
        count = sum(len(expand(pattern)) for pattern in patterns)
        print(f"- {category}: {count} inventoried file(s)")
    print("- stories: explicitly empty; generic stories remain outside BOD-CUAS")
    print("- airport-pack component references stay inside BOD-CUAS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
