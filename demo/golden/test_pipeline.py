#!/usr/bin/env python3
"""Smoke-test the canonical synthetic C-UAS projection path.

The test owns only the broker and the external furia-cuas publisher; Core is
not a C-UAS decision engine and the historical in-process service is not
started.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
LOG_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "furia-bod-golden"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> socket.socket:
    parsed = urlparse(NATS_URL)
    sock = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 4222), 10)
    sock.settimeout(10)
    sock.recv(4096)
    sock.sendall(b'CONNECT {"verbose":false}\r\nPING\r\n')
    sock.recv(4096)
    return sock


def main() -> int:
    parsed = urlparse(NATS_URL)
    nats = subprocess.Popen(
        ["nats-server", "-p", str(parsed.port or 4222), "-js", "-sd", str(LOG_DIR / "jetstream")],
        stdout=(LOG_DIR / "nats.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    publisher = None
    try:
        time.sleep(2)
        if nats.poll() is not None:
            return 1
        publisher_bin = Path(os.environ.get(
            "FURIA_CUAS_PUBLISHER_BIN",
            str(ROOT / "furia-cuas/target/release/furia-cuas-publisher"),
        ))
        if not publisher_bin.is_file():
            raise SystemExit(f"missing canonical publisher: {publisher_bin}")
        publisher = subprocess.Popen(
            [str(publisher_bin), "--nats-url", NATS_URL, "--simulate", "--ticks", "3", "--interval-ms", "100"],
            stdout=(LOG_DIR / "furia-cuas-publisher.log").open("w"),
            stderr=subprocess.STDOUT,
            env={**os.environ, "NATS_URL": NATS_URL},
        )
        subscriber = connect()
        subscriber.sendall(b"SUB furia.cuas.operational-projection 1\r\n")
        deadline = time.time() + 10
        payload = None
        while time.time() < deadline:
            data = subscriber.recv(65536)
            marker = data.find(b"MSG furia.cuas.operational-projection")
            if marker < 0:
                continue
            header_end = data.find(b"\r\n", marker)
            size = int(data[marker:header_end].split()[-1])
            body = data[header_end + 2:header_end + 2 + size]
            payload = json.loads(body)
            break
        subscriber.close()
        if not payload:
            raise RuntimeError("canonical projection was not observed")
        assert payload["schema"] == "furia.cuas.operational-projection"
        assert payload["version"] == "2.0.0"
        assert payload["producer"] == "furia-cuas-publisher"
        print("canonical furia-cuas projection: passed")
        return 0
    finally:
        for proc in (publisher, nats):
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
