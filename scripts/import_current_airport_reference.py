#!/usr/bin/env python3
"""Import current public airport reference coordinates without creating geodata packs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
FRENCH_TERRITORY_CODES = {"FR", "GP", "MQ", "PF", "RE", "GF", "NC"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_reference(inventory: dict, airports_csv: Path, runways_csv: Path, retrieved_at: str | None = None, aliases: dict[str, str] | None = None) -> dict:
    airports = {}
    with airports_csv.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            ident = (row.get("icao_code") or row.get("ident") or "").upper()
            if ident and row.get("iso_country") in FRENCH_TERRITORY_CODES and row.get("latitude_deg") and row.get("longitude_deg"):
                airports[ident] = row
    runways: dict[str, list[dict]] = {}
    with runways_csv.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            ident = (row.get("airport_ident") or "").upper()
            if ident in airports and row.get("closed") != "1":
                runways.setdefault(ident, []).append({
                    "length_ft": row.get("length_ft"),
                    "width_ft": row.get("width_ft"),
                    "surface": row.get("surface"),
                    "le_ident": row.get("le_ident"),
                    "he_ident": row.get("he_ident"),
                })
    entries = []
    aliases = aliases or {}
    for item in inventory["airports"]:
        ident = item["icao"]
        reference_ident = aliases.get(ident, ident)
        row = airports.get(reference_ident)
        entry = {
            "icao": ident,
            "name_inventory": item["name"],
            "iata_inventory": item.get("iata"),
            "source_status": "matched_current_reference" if row else "not_matched_current_reference",
            "source_country_code": (row or {}).get("iso_country"),
            "reference_icao": reference_ident if row else None,
            "reference_alias_used": reference_ident != ident if row else False,
            "operational_status": "not_operational",
            "pack_status": item.get("pack_status", "unknown"),
            "reference_point": None,
            "runways": runways.get(ident, []),
            "geometry_use": "candidate_bbox_input_only" if row else "requires_manual_source_resolution",
        }
        if row:
            entry["reference_point"] = {
                "latitude": float(row["latitude_deg"]),
                "longitude": float(row["longitude_deg"]),
                "elevation_ft": float(row["elevation_ft"]) if row.get("elevation_ft") else None,
            }
        entries.append(entry)
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema": "bod-cuas.current-airport-reference",
        "version": "1.0.0",
        "retrieved_at": timestamp,
        "status": "reference_only",
        "operational_claim": "none",
        "source": {
            "provider": "OurAirports",
            "airports_url": AIRPORTS_URL,
            "runways_url": RUNWAYS_URL,
            "license": "Public domain; no guarantee of accuracy or fitness for use",
            "airports_sha256": sha256(airports_csv),
            "runways_sha256": sha256(runways_csv),
        },
        "limitations": [
            "Référence publique actuelle, non certifiée par l’autorité aéronautique",
            "Ne remplace pas AIP, TOD, NOTAM, base d’obstacles ou données exploitant",
            "Les coordonnées ne constituent pas une emprise DEM/bâtiments",
        ],
        "summary": {
            "inventory_total": len(entries),
            "matched": sum(e["reference_point"] is not None for e in entries),
            "unmatched": sum(e["reference_point"] is None for e in entries),
        },
        "airports": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--airports-csv", type=Path, required=True)
    parser.add_argument("--runways-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--aliases", type=Path, default=None)
    args = parser.parse_args()
    alias_map = {}
    if args.aliases:
        alias_data = json.loads(args.aliases.read_text(encoding="utf-8"))
        alias_map = {item["inventory_icao"]: item["reference_icao"] for item in alias_data.get("aliases", [])}
    result = import_reference(json.loads(args.inventory.read_text(encoding="utf-8")), args.airports_csv, args.runways_csv, aliases=alias_map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
