#!/usr/bin/env python3
"""Replay deterministic Bordeaux C-UAS ASTERIX fixtures through Furia Core.

Publishes one already-framed record per JSON envelope to `surveillance.asterix.record`,
which is the production ingress owned by `counter-uas-director`.

No third-party Python packages are required: this script speaks the minimal NATS text
protocol over TCP.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

SUBJECT = "surveillance.asterix.record"


def _wgs84_raw(value_e7: int, fractional_bits: int) -> list[int]:
    raw = round(value_e7 * (1 << fractional_bits) / 1_800_000_000)
    return list(int(raw).to_bytes(4, "big", signed=True))


def _cat129(manufacturer: bytes, model: bytes, serial: bytes) -> list[int]:
    if len(manufacturer) != 3 or len(model) != 3 or len(serial) != 12:
        raise ValueError("CAT129 demo identity fields must be 3/3/12 bytes")

    # CAT129 Ed. 1.2 bounded Core profile:
    # FRN1,3,4,5,6,7 + FX; FRN8,9,11,14 + FX; FRN15.
    return [
        0xBF, 0xD3, 0x80,
        1, 2,                                      # SAC/SIC
        *manufacturer,
        *model,
        *serial,
        ord("F"), ord("R"),                       # registration country
        0, 0, 128,                                 # UTC time = 1 s after midnight
        *_wgs84_raw(448_300_000, 30),              # ~44.83 N
        *_wgs84_raw(-6_900_000, 30),               # ~0.69 W
        0, 1, 244,                                 # 50 m MSL (500 dm)
        0, 5,                                      # 5 m GNSS accuracy
        0x00, 0x06, 0x40, 0x00, 0xC8,             # E=1 m/s, N=2 m/s
        0, 0, 100,                                 # climb 1 m/s
    ]


def cat129_authorized() -> list[int]:
    return _cat129(b"DJI", b"M30", bytes(range(1, 13)))


def cat129_unknown() -> list[int]:
    return _cat129(b"DJI", b"M30", bytes([0xAA] * 12))


def cat129_expired() -> list[int]:
    return _cat129(b"DEM", b"EXP", bytes([0xEE] * 12))


def cat016_pair_configuration() -> list[int]:
    # CAT016 Ed. 1.0: FRN1,2,3,4,6; one Pair ID mapping.
    return [
        0xF4,
        1, 2,              # reporting SAC/SIC
        7,                 # service identification
        2,                 # Tx/Rx configuration message
        0, 0, 128,         # UTC time
        1,                 # REP
        0x10, 0x02,        # Pair ID
        0x20, 0x02,        # transmitter ID
        0x30, 0x02,        # receiver ID
    ]


def cat015_non_cooperative_target() -> list[int]:
    # CAT015 Ed. 1.2: FRN1,2,3,6,7 + FX; FRN12,13.
    return [
        0xE7, 0x0C,
        1, 2,                                      # SAC/SIC
        1,                                         # message type
        0, 7,                                      # service/sequence fields in bounded profile
        0, 0, 128,                                 # UTC time
        0x12, 0x34,                                # source track number
        0x10, 0x02, 0x00, 0x01, 0x23,             # Pair ID 0x1002 + observation 0x123
        0x80,                                      # position compound: P84 only
        *_wgs84_raw(448_300_000, 31),              # ~44.83 N
        *_wgs84_raw(-6_900_000, 31),               # ~0.69 W
    ]


def cat063_degraded_sensor() -> list[int]:
    # CAT063 Ed. 1.7: FRN1,3,4,5.
    return [
        0xB8,
        1, 2,              # reporting SAC/SIC
        0, 0, 128,         # UTC time
        3, 4,              # referenced sensor SAC/SIC
        0x40,              # degraded, FX=0
    ]


@dataclass(frozen=True)
class Fixture:
    label: str
    category: int
    record: list[int]
    altitude_msl_mm: int | None = None
    ground_elevation_msl_mm: int | None = None


FIXTURES = (
    Fixture("CAT016 pair configuration", 16, cat016_pair_configuration()),
    Fixture("CAT129 authorized inspection UAS", 129, cat129_authorized()),
    Fixture("CAT129 authorization unknown", 129, cat129_unknown()),
    Fixture("CAT129 known but expired/unauthorized", 129, cat129_expired()),
    Fixture("CAT015 non-cooperative target", 15, cat015_non_cooperative_target(), altitude_msl_mm=50_000),
    Fixture("CAT063 degraded sensor", 63, cat063_degraded_sensor()),
)


class NatsConnection:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "nats" or not parsed.hostname:
            raise ValueError("NATS URL must look like nats://host:4222")
        self.host = parsed.hostname
        self.port = parsed.port or 4222
        self.sock: socket.socket | None = None

    def __enter__(self) -> "NatsConnection":
        sock = socket.create_connection((self.host, self.port), timeout=5)
        sock.settimeout(5)
        self.sock = sock

        # Consume the server INFO line, then establish a quiet client connection.
        self._read_line()
        connect = json.dumps(
            {
                "verbose": False,
                "pedantic": False,
                "lang": "python",
                "version": "bod-cuas-stdlib-replay-v1",
                "protocol": 1,
            },
            separators=(",", ":"),
        ).encode()
        sock.sendall(b"CONNECT " + connect + b"\r\nPING\r\n")
        self._wait_for_pong()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _read_line(self) -> bytes:
        if self.sock is None:
            raise RuntimeError("NATS connection is not open")
        data = bytearray()
        while not data.endswith(b"\r\n"):
            chunk = self.sock.recv(1)
            if not chunk:
                raise ConnectionError("NATS connection closed")
            data.extend(chunk)
        return bytes(data[:-2])

    def _wait_for_pong(self) -> None:
        while True:
            line = self._read_line()
            if line == b"PONG":
                return
            if line == b"PING":
                assert self.sock is not None
                self.sock.sendall(b"PONG\r\n")
            elif line.startswith(b"-ERR"):
                raise RuntimeError(f"NATS error: {line.decode(errors='replace')}")

    def publish_json(self, subject: str, value: dict[str, object]) -> None:
        if self.sock is None:
            raise RuntimeError("NATS connection is not open")
        payload = json.dumps(value, separators=(",", ":")).encode()
        header = f"PUB {subject} {len(payload)}\r\n".encode()
        self.sock.sendall(header + payload + b"\r\nPING\r\n")
        self._wait_for_pong()


def envelope(fixture: Fixture) -> dict[str, object]:
    return {
        "category": fixture.category,
        "record": fixture.record,
        "received_at_ms": int(time.time() * 1000),
        "altitude_msl_mm": fixture.altitude_msl_mm,
        "ground_elevation_msl_mm": fixture.ground_elevation_msl_mm,
    }


def replay(url: str, delay_s: float) -> None:
    with NatsConnection(url) as nats:
        for fixture in FIXTURES:
            nats.publish_json(SUBJECT, envelope(fixture))
            print(f"published: {fixture.label}")
            if delay_s > 0:
                time.sleep(delay_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats", default="nats://127.0.0.1:4222", help="NATS server URL")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between fixtures")
    parser.add_argument("--loop", action="store_true", help="repeat the fixture sequence")
    args = parser.parse_args()

    while True:
        replay(args.nats, max(args.delay, 0.0))
        if not args.loop:
            return 0
        time.sleep(max(args.delay, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
