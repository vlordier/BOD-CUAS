#!/usr/bin/env python3
"""Fetch, cache and normalize public aviation context for the LFBD demo.

This module is intentionally display-only.  It never creates authority,
clearances, response requests or C-UAS commands.  Network responses are
stored as immutable-ish snapshots so a presentation can be repeated without
depending on the public service being available at show time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_bridge import (  # noqa: E402
    OBSERVATION_SUBJECT,
    PROVENANCE_SUBJECT,
    WEATHER_SUBJECT,
    NatsPublisher,
    adapt_adsb,
    adapt_weather,
    now_ms,
    raw_digest,
    source_provenance,
)

OPENSKY_URL = "https://opensky-network.org/api/states/all"
AVIATION_WEATHER_URL = "https://aviationweather.gov/api/data/metar"


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def fetch_snapshot(url: str, cache_dir: Path, *, max_age_sec: int = 300, no_network: bool = False) -> tuple[Any, dict[str, Any]]:
    """Return payload plus explicit cache/network provenance."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{_cache_key(url)}.json"
    now = int(time.time())
    if path.exists():
        cached = json.loads(path.read_text())
        age = max(0, now - int(cached["fetched_at_unix"]))
        if no_network or age <= max_age_sec:
            return cached["payload"], {"mode": "cache", "age_sec": age, "path": str(path), "sha256": cached["sha256"]}
    if no_network:
        raise RuntimeError(f"no usable cached snapshot for {url}")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Furia-CUAS-demo-context/1.0"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    path.write_text(json.dumps({"schema": "furia.cuas.public-context-snapshot", "version": "1.0.0", "url": url, "fetched_at_unix": now, "sha256": digest, "payload": payload}, indent=2) + "\n")
    return payload, {"mode": "network", "age_sec": 0, "path": str(path), "sha256": digest}


def opensky_url(*, lamin: float = 44.65, lamax: float = 45.05, lomin: float = -1.05, lomax: float = -0.35) -> str:
    return f"{OPENSKY_URL}?{urlencode({'lamin': lamin, 'lamax': lamax, 'lomin': lomin, 'lomax': lomax})}"


def opensky_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OpenSky state vectors to the bridge's receiver-neutral shape."""
    records: list[dict[str, Any]] = []
    for state in payload.get("states", []) or []:
        if not isinstance(state, list) or len(state) < 11 or state[6] is None or state[5] is None:
            continue
        records.append({
            "icao24": str(state[0]),
            "callsign": (str(state[1]).strip() if state[1] else None),
            "longitude": float(state[5]),
            "latitude": float(state[6]),
            "altitude_msl_m": float(state[7] or state[13] or 0),
            "on_ground": bool(state[8]),
            "ground_speed_mps": float(state[9] or 0),
            "track_deg": float(state[10] or 0),
            "vertical_speed_mps": float(state[11] or 0),
            "observed_at_ms": int(float(payload.get("time", time.time())) * 1000),
        })
    return records


def adapt_opensky(payload: dict[str, Any], source: dict[str, Any], received_at_ms: int) -> list[dict[str, Any]]:
    events = []
    for record in opensky_records(payload):
        event = adapt_adsb(record, source, received_at_ms)
        event["observation"]["provenance"]["profile"] = "opensky_state_vector_context"
        event["observation"]["provenance"]["raw_record_sha256"] = raw_digest(record)
        event["observation"]["identity"] = f"adsb:{record['icao24']}"
        event["observation"]["context_only"] = True
        events.append(event)
    return events


def build_public_context(*, cache_dir: Path, no_network: bool = False, max_age_sec: int = 300) -> dict[str, Any]:
    """Fetch one bounded traffic/weather snapshot for a repeatable demo."""
    received = now_ms()
    traffic_url = opensky_url()
    traffic, traffic_meta = fetch_snapshot(traffic_url, cache_dir, max_age_sec=max_age_sec, no_network=no_network)
    weather_url = f"{AVIATION_WEATHER_URL}?{urlencode({'ids': 'LFBD', 'format': 'json'})}"
    weather, weather_meta = fetch_snapshot(weather_url, cache_dir, max_age_sec=max_age_sec, no_network=no_network)
    source_traffic = {"id": "lfbd-opensky", "kind": "opensky_state_vectors", "provider": "OpenSky Network", "edition": "REST-state-v1", "airport_icao": "LFBD"}
    source_weather = {"id": "lfbd-aviation-weather", "kind": "metar_http_json", "provider": "AviationWeather.gov", "airport_icao": "LFBD"}
    return {
        "schema": "furia.cuas.mixed-context-snapshot", "version": "1.0.0", "airport_icao": "LFBD",
        "captured_at_ms": received, "limitations": ["Context only; not ATC truth.", "Public feeds may be delayed, incomplete or unavailable.", "Synthetic threat and response data remain separate."],
        "feeds": [
            {**source_provenance(source_traffic, "nominal", received, f"{len(opensky_records(traffic))} OpenSky state vector(s); snapshot={traffic_meta['mode']}"), "snapshot": traffic_meta},
            {**source_provenance(source_weather, "nominal", received, f"LFBD METAR; snapshot={weather_meta['mode']}"), "snapshot": weather_meta},
        ],
        "traffic_events": adapt_opensky(traffic, source_traffic, received),
        "weather_event": adapt_weather(weather, source_weather, received),
    }


def publish_context(snapshot: dict[str, Any], publisher: NatsPublisher) -> int:
    """Publish only context subjects; return the number of emitted messages."""
    count = 0
    for event in snapshot["traffic_events"]:
        publisher.publish(OBSERVATION_SUBJECT, event)
        count += 1
    publisher.publish(WEATHER_SUBJECT, snapshot["weather_event"])
    count += 1
    for feed in snapshot["feeds"]:
        publisher.publish(PROVENANCE_SUBJECT, feed)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="data/live-context-cache")
    parser.add_argument("--output", default="data/lfbd-mixed-context.json")
    parser.add_argument("--max-age-sec", type=int, default=300)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--nats-url", default=None, help="Publish context-only subjects to this NATS URL")
    parser.add_argument("--dry-run", action="store_true", help="Print publish subjects without connecting")
    args = parser.parse_args()
    result = build_public_context(cache_dir=Path(args.cache_dir), no_network=args.no_network, max_age_sec=args.max_age_sec)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {output}: {len(result['traffic_events'])} traffic event(s)")
    if args.nats_url:
        if args.dry_run:
            print(f"would publish {len(result['traffic_events']) + len(result['feeds']) + 1} context-only event(s)")
        else:
            publisher = NatsPublisher(args.nats_url)
            try:
                print(f"published {publish_context(result, publisher)} context-only event(s)")
            finally:
                publisher.close()


if __name__ == "__main__":
    main()
