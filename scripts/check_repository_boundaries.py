#!/usr/bin/env python3
"""Fail-fast checks for cross-repository ownership boundaries.

This is intentionally a small static check. It does not attempt to replace
Cargo/TypeScript dependency checks; it catches the accidental imports that
would turn an airport scenario or host into a shared primitive owner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REQUIRED_REPOSITORIES = {
    "bod_cuas": "BOD-CUAS",
    "furia_core": "furia-core",
    "furia_cuas": "furia-cuas",
    "furia_ui": "furia-ui",
    "furia_c2": "furia-c2",
}


def source_files(root: Path, *parts: str):
    base = root.joinpath(*parts)
    if not base.exists():
        return []
    return [path for path in base.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".mjs", ".rs"}]


def find_forbidden(files: list[Path], needles: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(needle in line for needle in needles):
                violations.append(f"{path}:{line_number}: {line.strip()}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    boundary_path = root / "BOD-CUAS/contracts/repository-boundary.json"

    try:
        boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"boundary manifest invalid: {error}", file=sys.stderr)
        return 1

    repositories = boundary.get("repositories", {})
    errors = []
    for key, relative_path in REQUIRED_REPOSITORIES.items():
        declared = repositories.get(key, {}).get("path")
        if declared != relative_path:
            errors.append(f"{key}: declared path must be {relative_path!r}, got {declared!r}")
        if not (root / relative_path).is_dir():
            errors.append(f"{key}: repository directory missing: {root / relative_path}")

    ui_files = source_files(root, "furia-ui/packages/ui/src")
    c2_files = source_files(root, "furia-c2/src")
    cuas_files = source_files(root, "furia-cuas/crates")
    errors.extend(find_forbidden(ui_files, ("BOD-CUAS/demo/", "../BOD-CUAS", "from 'furia-c2/src")))
    errors.extend(find_forbidden(c2_files, ("BOD-CUAS/demo/", "../BOD-CUAS", "furia-ui/packages/ui/src")))
    errors.extend(find_forbidden(cuas_files, ("furia-ui/packages/ui", "BOD-CUAS/demo/", "furia-c2/src")))

    if errors:
        print("repository boundary check: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("repository boundary check: PASS")
    print("- airport fixtures remain in BOD-CUAS")
    print("- generic C-UAS contracts remain in furia-cuas/furia-core")
    print("- UI and C2 do not import sibling implementation paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
