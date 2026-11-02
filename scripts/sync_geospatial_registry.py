#!/usr/bin/env python3
"""Synchronise the context-pack registry with validated geospatial packs.

The registry remains explicitly partial in an operational sense: the identity
inventory is historical and no entry is promoted to operational use by this
script. It only prevents a valid on-disk pack from being invisible to the
registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def sync(registry_path: Path, inventory_path: Path, root: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    entries = {item["icao"]: item for item in registry.get("airports", [])}
    for airport in inventory["airports"]:
        icao = airport["icao"]
        manifest = root / "data" / "geospatial" / icao.lower() / "manifest.json"
        if not manifest.exists():
            continue
        entry = entries.get(icao, {})
        entry.update({
            "icao": icao,
            "pack_manifest": f"data/geospatial/{icao.lower()}/manifest.json",
            "geospatial_manifest": f"data/geospatial/{icao.lower()}/manifest.json",
            "status": "context_only_pending_review",
            "data_claim": "Pack DEM IGN et bâtiments OSM présents; emprise dérivée ou revue requise; contexte de simulation uniquement.",
            "missing_before_operational_use": [
                "source aéronautique et exploitant courants",
                "validation géométrique indépendante",
                "référence verticale et exactitude vérifiées",
                "inventaire obstacles/bâtiments complet et daté",
            ],
        })
        entries[icao] = entry
    registry["airports"] = [entries[icao] for icao in sorted(entries)]
    registry["description"] = "Registre de tous les packs géospatiaux présents dans ce dépôt; l’identité de référence reste historique et chaque entrée demeure context_only jusqu’à validation autorité/exploitant."
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"registry_entries": len(registry["airports"]), "pack_entries": sum((root / "data" / "geospatial" / item["icao"].lower() / "manifest.json").exists() for item in inventory["airports"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sync(args.registry, args.inventory, args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
