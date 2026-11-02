#!/usr/bin/env python3
"""Bridge real C-UAS context into the Bordeaux NATS integration boundary.

The bridge deliberately has no authority or command capability.  It can turn
local ADS-B and Remote ID receiver exports into the *existing*, versioned
``surveillance.observation`` contract, and publish weather/feed provenance as
display-only context.  Airport/ATC, U-space and countermeasure feeds are never
simulated as authoritative data by this process.

Only Python's standard library is used so it can run beside the golden demo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen
from urllib.parse import urlparse

OBSERVATION_SUBJECT = "surveillance.observation"
WEATHER_SUBJECT = "environment.weather.observation"
PROVENANCE_SUBJECT = "cuas.feed.provenance"


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_track_id(value: str) -> int:
    """Produce a positive u32 source track id without exposing raw identifiers."""
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big") & 0x7FFF_FFFF


def raw_digest(record: dict[str, Any]) -> list[int]:
    return list(hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).digest())


def metres_to_mm(value: Any) -> int:
    return int(round(float(value) * 1000))


def adapt_adsb(record: dict[str, Any], source: dict[str, Any], received_at_ms: int) -> dict[str, Any]:
    """Adapt a local ADS-B receiver record to CAT021-equivalent Core input."""
    icao24 = str(record["icao24"]).strip().lower()
    lat, lon = float(record["latitude"]), float(record["longitude"])
    altitude = record.get("altitude_msl_m", record.get("altitude_m", 0))
    speed = float(record.get("ground_speed_mps", 0))
    heading = float(record.get("track_deg", 0))
    import math
    north = int(round(speed * math.cos(math.radians(heading)) * 1000))
    east = int(round(speed * math.sin(math.radians(heading)) * 1000))
    observed = int(record.get("observed_at_ms", received_at_ms))
    if observed > received_at_ms:
        observed = received_at_ms
    return {"observation": {
        "kind": "crewed_aircraft", "observed_at_ms": observed,
        "position": {"latitude_e7": round(lat * 10_000_000), "longitude_e7": round(lon * 10_000_000), "altitude_msl_mm": metres_to_mm(altitude)},
        "velocity_ned_mm_s": [north, east, int(round(-float(record.get("vertical_speed_mps", 0)) * 1000))],
        "horizontal_uncertainty_mm": int(source.get("horizontal_uncertainty_mm", 150)),
        "vertical_uncertainty_mm": int(source.get("vertical_uncertainty_mm", 250)),
        "cooperative": True, "authorized": None, "identity": f"adsb:{icao24}",
        "provenance": {"category": 21, "edition": str(source.get("edition", "local-receiver/v1")), "profile": "local_adsb_receiver",
          "sac": source.get("sac"), "sic": source.get("sic"), "source_track_id": stable_track_id(icao24), "pair_id": None,
          "received_at_ms": received_at_ms, "raw_record_sha256": raw_digest(record)}}}


def adapt_remote_id(record: dict[str, Any], source: dict[str, Any], received_at_ms: int) -> dict[str, Any]:
    """Adapt a receiver-decoded Remote ID record; authorization stays unknown."""
    identifier = str(record.get("uas_id") or record.get("serial_number") or record["id"]).strip()
    lat, lon = float(record["latitude"]), float(record["longitude"])
    altitude = record.get("altitude_msl_m", record.get("altitude_m", 0))
    observed = min(int(record.get("observed_at_ms", received_at_ms)), received_at_ms)
    return {"observation": {
        "kind": "cooperative_uas", "observed_at_ms": observed,
        "position": {"latitude_e7": round(lat * 10_000_000), "longitude_e7": round(lon * 10_000_000), "altitude_msl_mm": metres_to_mm(altitude)},
        "velocity_ned_mm_s": [int(record.get("north_mms", 0)), int(record.get("east_mms", 0)), int(record.get("down_mms", 0))],
        "horizontal_uncertainty_mm": int(source.get("horizontal_uncertainty_mm", 500)),
        "vertical_uncertainty_mm": int(source.get("vertical_uncertainty_mm", 750)),
        "cooperative": True, "authorized": None, "identity": f"remote-id:{identifier}",
        "provenance": {"category": 129, "edition": str(source.get("edition", "ASTM-F3411-receiver/v1")), "profile": "local_remote_id_receiver",
          "sac": source.get("sac"), "sic": source.get("sic"), "source_track_id": stable_track_id(identifier), "pair_id": None,
          "received_at_ms": received_at_ms, "raw_record_sha256": raw_digest(record)}}}


def adapt_weather(payload: Any, source: dict[str, Any], received_at_ms: int) -> dict[str, Any]:
    """Preserve raw provider material; it is display context, never safety truth."""
    report = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else payload
    return {"schema": "furia.cuas.weather-observation", "version": "1.0.0", "observed_at_ms": received_at_ms,
            "provider": source.get("provider", "configured-weather-provider"), "airport_icao": source.get("airport_icao", "LFBD"),
            "provenance": "external_context_unvalidated", "raw": report,
            "raw_metar": report.get("rawOb") if isinstance(report, dict) else None}


class NatsPublisher:
    def __init__(self, nats_url: str) -> None:
        parsed = urlparse(nats_url)
        self.sock = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 4222), timeout=10)
        self.sock.recv(4096)
        self.sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"live-context-bridge","version":"1"}\r\nPING\r\n')
        self.sock.recv(4096)

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.sock.sendall(f"PUB {subject} {len(encoded)}\r\n".encode() + encoded + b"\r\nPING\r\n")
        self.sock.recv(4096)

    def close(self) -> None:
        self.sock.close()


def jsonl_records(path: Path) -> Iterable[dict[str, Any]]:
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            yield value


def fetch_json(source: dict[str, Any]) -> Any:
    headers = {"Accept": "application/json"}
    token_env = source.get("bearer_token_env")
    if token_env and os.environ.get(str(token_env)):
        headers["Authorization"] = f"Bearer {os.environ[str(token_env)]}"
    with urlopen(Request(str(source["url"]), headers=headers), timeout=float(source.get("timeout_sec", 10))) as response:
        return json.loads(response.read())


def source_provenance(source: dict[str, Any], health: str, received_at_ms: int, detail: str) -> dict[str, Any]:
    return {"schema": "furia.cuas.feed-provenance", "version": "1.0.0", "feed_id": source["id"],
            "kind": source["kind"], "provider": source.get("provider", source["id"]), "health": health,
            "observed_at_ms": received_at_ms, "received_at_ms": received_at_ms,
            "authority": "context_only", "detail": detail,
            "limitations": ["Not an ATC or airport-operational feed.", "Cannot create authority or trigger a response."]}


def sensor_status(source: dict[str, Any], health: str, received_at_ms: int) -> dict[str, Any]:
    """Emit CAT063-equivalent health without claiming sensor performance."""
    sac, sic = int(source.get("sac", 250)), int(source.get("sic", 0))
    state = "operational" if health == "nominal" else "degraded"
    return {"sensor_id": source.get("c2_sensor_id", source["id"]), "observation": {
        "kind": "sensor_status", "observed_at_ms": received_at_ms,
        "position": None, "velocity_ned_mm_s": None,
        "horizontal_uncertainty_mm": None, "vertical_uncertainty_mm": None,
        "cooperative": None, "authorized": None, "identity": None,
        "provenance": {"category": 63, "edition": "local-context-bridge/v1", "profile": "receiver_health",
          "sac": sac, "sic": sic, "source_track_id": None, "pair_id": None,
          "received_at_ms": received_at_ms,
          "raw_record_sha256": raw_digest({"source": source["id"], "health": health, "received_at_ms": received_at_ms})}},
        "sensor_sac": sac, "sensor_sic": sic, "connection_status": state}


def run_source(source: dict[str, Any], publisher: NatsPublisher | None, root: Path) -> list[tuple[str, dict[str, Any]]]:
    received = now_ms()
    kind = source["kind"]
    output: list[tuple[str, dict[str, Any]]] = []
    try:
        if kind in {"adsb_jsonl", "remote_id_jsonl"}:
            path = root / str(source["path"])
            records = list(jsonl_records(path))
            adapter = adapt_adsb if kind == "adsb_jsonl" else adapt_remote_id
            output.extend((OBSERVATION_SUBJECT, adapter(record, source, received)) for record in records)
            detail = f"{len(records)} local receiver record(s) normalized"
        elif kind == "metar_http_json":
            output.append((WEATHER_SUBJECT, adapt_weather(fetch_json(source), source, received)))
            detail = "weather context fetched"
        else:
            raise ValueError(f"unsupported source kind: {kind}")
        output.append(("surveillance.sensor.status", sensor_status(source, "nominal", received)))
        output.append((PROVENANCE_SUBJECT, source_provenance(source, "nominal", received, detail)))
    except Exception as error:
        output.append(("surveillance.sensor.status", sensor_status(source, "degraded", received)))
        output.append((PROVENANCE_SUBJECT, source_provenance(source, "degraded", received, str(error))))
    if publisher:
        for subject, payload in output:
            publisher.publish(subject, payload)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="context-sources.example.json")
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://127.0.0.1:4222"))
    parser.add_argument("--dry-run", action="store_true", help="validate and print payloads without publishing")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text())
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        raise SystemExit("config.sources must be a list")
    publisher = None if args.dry_run else NatsPublisher(args.nats_url)
    try:
        for source in sources:
            for subject, payload in run_source(source, publisher, config_path.parent):
                print(f"{subject} {json.dumps(payload, sort_keys=True)}")
    finally:
        if publisher:
            publisher.close()


if __name__ == "__main__":
    main()
