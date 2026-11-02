#!/usr/bin/env python3
"""Publish visual-world provenance for the LFBD training simulator.

This contract deliberately carries scene metadata only: it does not provide
runway state, obstacle authority, navigation, clearance, or mission inputs.
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import time
from urllib.parse import urlparse


def payload() -> dict:
    now = int(time.time() * 1000)
    return {
        "schema": "furia.cuas.visual-world-context", "version": "1.0.0",
        "world_id": "lfbd-bati3d-2012-training-context",
        "label": "LFBD · BATI3D 2012 VISUAL CONTEXT",
        "coverage_label": "1.4 × 1.0 KM · 35 HISTORICAL TEXTURED TILES",
        # This publisher emits deterministic training poses.  It must not imply
        # a live connection to a running RealGazebo/Unreal instance.
        "renderer": "Deterministic visual-world simulator",
        "provenance": "Bordeaux Métropole Bati3D (2012) · historical open context",
        "authority": "context_only", "observed_at_ms": now,
        "limitations": [
            "Historical 2012 visual backdrop; not current airport layout.",
            "Not an obstacle database, navigation source, airport operations feed, or EO/IR evidence.",
            "All runways, protected volumes and sensor sites remain separately labelled training geometry until a reviewed static import is supplied.",
        ],
    }


def state_payload() -> dict:
    """Deterministic, clearly simulated poses for the visual training world."""
    now = int(time.time() * 1000)
    phase = (now // 1000) % 90 / 90.0
    threat_lat, threat_lon = 44.846 - phase * 0.014, -0.699 - phase * 0.018
    return {
        "schema": "furia.cuas.visual-world-state", "version": "1.0.0",
        "world_id": "lfbd-bati3d-2012-training-context", "authority": "context_only", "observed_at_ms": now,
        "threat": {"latitude": threat_lat, "longitude": threat_lon, "altitude_m": round(82 + 9 * math.sin(phase * math.pi), 1)},
        "interceptor": {"id": "S1-03", "latitude": 44.833 + phase * 0.010, "longitude": -0.717 + phase * 0.010, "altitude_m": 70, "mode": "training_shadow"},
        "ptz": {"id": "PTZ-2", "latitude": 44.835, "longitude": -0.711, "mode": "slewing_to_track"},
        "controller_estimate": {"latitude": 44.8238, "longitude": -0.7249, "uncertainty_m": 310},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats-url", default="nats://127.0.0.1:4222")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=2.0,
                        help="republish interval; use 0 for a one-shot publication")
    args = parser.parse_args()
    message = payload()
    if args.dry_run:
        print(json.dumps(message, sort_keys=True))
        return
    parsed = urlparse(args.nats_url)
    with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 4222), timeout=10) as sock:
        sock.recv(4096)
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false}\r\nPING\r\n')
        sock.recv(4096)
        while True:
            body = json.dumps(payload(), separators=(",", ":")).encode()
            sock.sendall(f"PUB cuas.visual-world.context {len(body)}\r\n".encode() + body + b"\r\nPING\r\n")
            sock.recv(4096)
            state = json.dumps(state_payload(), separators=(",", ":")).encode()
            sock.sendall(f"PUB cuas.visual-world.state {len(state)}\r\n".encode() + state + b"\r\nPING\r\n")
            sock.recv(4096)
            print("published cuas.visual-world.context", flush=True)
            if args.interval_sec <= 0:
                return
            time.sleep(args.interval_sec)


if __name__ == "__main__":
    main()
