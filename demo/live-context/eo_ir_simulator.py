#!/usr/bin/env python3
"""Publish a deterministic, labelled EO/IR metadata stream for C2 rehearsal.

The messages resemble KLV-derived metadata but deliberately carry no video
pixels and always identify themselves as training simulation. A real RTSP or
STANAG 4609 adapter can publish the same ``video.metadata`` shape.
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import time
from urllib.parse import urlparse


def publish(sock: socket.socket, subject: str, payload: dict) -> None:
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(encoded)}\r\n".encode() + encoded + b"\r\nPING\r\n")
    sock.recv(4096)


def metadata(now_ms: int, tick: int) -> dict:
    phase = tick / 10
    return {
        "schema": "furia.cuas.video-metadata", "version": "1.0.0",
        "source_id": "PTZ-2", "source_label": "PTZ-2 · VISUAL",
        "provenance": "training_simulation", "transport": "simulated_klv",
        "recording": "training", "observed_at_ms": now_ms,
        "track_id": "4660", "classification": "uas_candidate",
        "confidence_permille": 810, "latency_ms": 118,
        "azimuth_deg": round(71 + math.sin(phase) * 1.7, 1), "elevation_deg": 2.1,
        "range_m": int(2150 - min(tick, 80) * 8),
        "target_x_permille": int(560 + math.sin(phase) * 90),
        "target_y_permille": int(340 + math.cos(phase * .7) * 55),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats-url", default="nats://127.0.0.1:4222")
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--duration-sec", type=float, default=0, help="0 = run until interrupted")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.nats_url)
    start = time.monotonic()
    tick = 0
    if args.dry_run:
        print(json.dumps(metadata(int(time.time() * 1000), tick), indent=2))
        return
    with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 4222), timeout=10) as sock:
        sock.recv(4096)
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false}\r\nPING\r\n')
        sock.recv(4096)
        while args.duration_sec <= 0 or time.monotonic() - start < args.duration_sec:
            now = int(time.time() * 1000)
            publish(sock, "video.metadata", metadata(now, tick))
            # Keep provenance on the same cadence as the metadata.  A source
            # health banner is only meaningful if its received timestamp is
            # current; publishing it every ten seconds made a healthy 1 Hz
            # simulation look "stale" for most of the operator replay.
            publish(sock, "cuas.feed.provenance", {
                "schema": "furia.cuas.feed-provenance", "version": "1.0.0",
                "feed_id": "lfbd-sim-eo-ir", "kind": "eo_ir_simulator",
                "provider": "BOD EO/IR metadata simulator", "health": "nominal",
                "observed_at_ms": now, "received_at_ms": now, "authority": "context_only",
                "limitations": ["Simulated KLV metadata; no live imagery.", "Cannot create authority or trigger a response."],
            })
            tick += 1
            time.sleep(args.interval_sec)


if __name__ == "__main__":
    main()
