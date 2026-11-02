#!/usr/bin/env python3
"""Resolve an airport-pack and emit runner-ready JSON."""
from __future__ import annotations

import argparse
import json
import sys

from airport_pack import resolve_airport_pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="path to an airport-pack manifest")
    args = parser.parse_args()
    try:
        print(json.dumps(resolve_airport_pack(args.manifest), ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
