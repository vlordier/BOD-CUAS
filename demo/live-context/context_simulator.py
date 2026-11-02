#!/usr/bin/env python3
"""Emit explicitly simulated external-context feeds for an offline C2 rehearsal.

This fills presentation gaps (weather, airport operational state, U-space
availability) without asserting that any airport, ANSP, or USSP is connected.
It never publishes an authorisation, mission command, or an ATC clearance.
"""
from __future__ import annotations

import argparse
import json
import socket
import time
from urllib.parse import urlparse


def publish(sock: socket.socket, subject: str, payload: dict) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(body)}\r\n".encode() + body + b"\r\nPING\r\n")
    sock.recv(4096)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats-url", default="nats://127.0.0.1:4222")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = int(time.time() * 1000)
    feeds = [
        ("cuas.feed.provenance", {"schema": "furia.cuas.feed-provenance", "version": "1.0.0", "feed_id": "lfbd-sim-weather", "kind": "metar_simulator", "provider": "BOD training weather simulator", "health": "nominal", "observed_at_ms": now, "received_at_ms": now, "authority": "context_only", "limitations": ["Simulated weather; not a flight release.", "Cannot create authority or trigger a response."]}),
        ("environment.weather.observation", {"schema": "furia.cuas.weather-observation", "version": "1.0.0", "airport_icao": "LFBD", "observed_at_ms": now, "provider": "simulation", "provenance": "training_simulation", "metar": "LFBD 251000Z 24008KT 9999 FEW020 18/11 Q1016"}),
        ("cuas.feed.provenance", {"schema": "furia.cuas.feed-provenance", "version": "1.0.0", "feed_id": "lfbd-sim-airport-ops", "kind": "airport_ops_simulator", "provider": "BOD training airport operations simulator", "health": "nominal", "observed_at_ms": now, "received_at_ms": now, "authority": "context_only", "limitations": ["Simulated airport state; not AODB or ATC data.", "Cannot create authority or trigger a response."]}),
        ("airport.operations.context", {"schema": "furia.cuas.airport-operations-context", "version": "1.0.0", "airport_icao": "LFBD", "provenance": "training_simulation", "active_runway": "05/23", "runway_state": "monitored", "atc_acknowledgement": "not_connected", "observed_at_ms": now}),
        ("cuas.feed.provenance", {"schema": "furia.cuas.feed-provenance", "version": "1.0.0", "feed_id": "lfbd-sim-uspace", "kind": "uspace_simulator", "provider": "BOD training U-space simulator", "health": "nominal", "observed_at_ms": now, "received_at_ms": now, "authority": "context_only", "limitations": ["Simulated U-space availability; not a USSP/CISP integration.", "Cannot create authority or trigger a response."]}),
        ("uspace.network-identification.context", {"schema": "furia.cuas.uspace-context", "version": "1.0.0", "airport_icao": "LFBD", "provenance": "training_simulation", "network_identification": "unavailable", "flight_authorisation": "not_connected", "observed_at_ms": now}),
    ]
    if args.dry_run:
        for subject, payload in feeds:
            print(subject, json.dumps(payload, sort_keys=True))
        return
    parsed = urlparse(args.nats_url)
    with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 4222), timeout=10) as sock:
        sock.recv(4096)
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false}\r\nPING\r\n')
        sock.recv(4096)
        for subject, payload in feeds:
            publish(sock, subject, payload)
            print(f"published {subject}")


if __name__ == "__main__":
    main()
