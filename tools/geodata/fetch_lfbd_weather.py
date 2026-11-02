#!/usr/bin/env python3
"""Fetch a public, non-authoritative LFBD weather snapshot for simulation."""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://api.open-meteo.com/v1/forecast?latitude=44.8286&longitude=-0.7153&current=wind_speed_10m,wind_direction_10m,visibility,precipitation,cloud_cover&wind_speed_unit=kn&timezone=UTC"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/geospatial/lfbd/weather.json"))
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    with urllib.request.urlopen(urllib.request.Request(args.url, headers={"User-Agent": "Furia-CUAS-weather-importer/1.0"}), timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    current = data.get("current", {})
    output = {
        "schema": "furia.cuas.weather-snapshot",
        "version": "1.0.0",
        "airport_icao": "LFBD",
        "source": "Open-Meteo",
        "source_url": args.url,
        "license": "CC BY 4.0 · attribution required",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": current.get("time"),
        "wind_kt": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "visibility_m": current.get("visibility"),
        "precipitation_mm": current.get("precipitation"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "provenance": "external_public_context",
        "limitations": ["Ne constitue pas un METAR ni une donnée météo aéronautique certifiée", "Utiliser Météo-France ou le fournisseur aéroportuaire pour un usage opérationnel"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched LFBD weather -> {args.output}")


if __name__ == "__main__":
    main()
