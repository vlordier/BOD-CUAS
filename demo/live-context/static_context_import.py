#!/usr/bin/env python3
"""Validate and fingerprint a curated airport GeoJSON import for C2 context.

This is an import boundary, not an AIP/TOD parser. Downloaded SIA AIXM/TOD
material must be converted by a reviewed source-specific process to GeoJSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="static-context-source.example.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    input_path = manifest_path.parent / manifest["geojson_path"]
    raw = input_path.read_bytes()
    geojson = json.loads(raw)
    if not isinstance(geojson.get("features"), list):
        raise SystemExit("expected an object with a features list")
    for feature in geojson["features"]:
        if not feature.get("geometry", {}).get("type"):
            raise SystemExit("every feature must have a geometry")
    output = {
        "schema": "furia.cuas.airport-static-context", "version": "1.0.0",
        "airport_icao": manifest["airport_icao"], "provenance": manifest["provenance"],
        "airac_cycle": manifest.get("airac_cycle"), "effective_from": manifest.get("effective_from"),
        "source_url": manifest["source_url"], "license": manifest["license"],
        "sha256": hashlib.sha256(raw).hexdigest(), "feature_count": len(geojson["features"]),
        "limitations": ["C2 context only; not a navigation, clearance or obstacle-avoidance product."],
        "geojson": geojson,
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {args.output}: {output['feature_count']} features sha256={output['sha256']}")


if __name__ == "__main__":
    main()
