"""Audit every inventoried airport without fabricating missing geodata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_geospatial_provenance import validate_manifest


def audit(root: Path, inventory_path: Path) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    results = []
    for airport in inventory["airports"]:
        icao = airport["icao"]
        manifest = root / "data" / "geospatial" / icao.lower() / "manifest.json"
        result: dict[str, Any] = {
            "icao": icao,
            "name": airport["name"],
            "identity_source": inventory["source_id"],
            "identity_status": "historical_reference",
            "operational_status": "not_operational",
            "geospatial_manifest": str(manifest.relative_to(root)) if manifest.exists() else None,
            "status": "missing_pack",
            "checks": [],
        }
        if manifest.exists():
            try:
                result["checks"] = validate_manifest(manifest, root)
                result["status"] = "context_only"
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                result["status"] = "invalid_pack"
                result["error"] = str(error)
        results.append(result)
    summary = {
        "inventoried": len(results),
        "context_only": sum(item["status"] == "context_only" for item in results),
        "missing_pack": sum(item["status"] == "missing_pack" for item in results),
        "invalid_pack": sum(item["status"] == "invalid_pack" for item in results),
    }
    return {
        "schema": "bod-cuas.airport-geospatial-readiness-audit",
        "version": "1.0.0",
        "source_inventory": inventory["source_id"],
        "source_inventory_status": inventory["status"],
        "operational_claim": "none",
        "summary": summary,
        "airports": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory = (args.inventory or root / "data/geospatial/france-airports-identity-inventory.json").resolve()
    result = audit(root, inventory)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 1 if result["summary"]["invalid_pack"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
