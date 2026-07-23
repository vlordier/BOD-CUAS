# Bordeaux Airport C-UAS Golden Demo — Presenter's Guide

## Overview

This demo proves the full multi-repository runtime chain for a C-UAS scenario at Bordeaux Airport (LFBD). The scenario is deterministic, replayable, and fail-closed.

## Authority Boundaries

| Layer | Owns | Never |
|-------|------|-------|
| **Core** (furia-core) | ASTERIX ingestion, surveillance fusion, authorization, mission delegation, safety abort | Cannot delegate without operator authorization |
| **S1** (S1) | Local execution safety, degraded-mode continuation, abort execution | Cannot create or extend mission authority |
| **C2** (furia-c2) | Read-only visualization | Cannot invent authorization, admit evidence, or generate safety decisions |
| **Replay** (BOD-CUAS) | Stimuli/facts only | Never publishes authoritative outputs |

## Scenario Timeline

| Time | Event | Published By | Authority |
|------|-------|-------------|-----------|
| 0s | Scenario starts | Replay | Stimulus |
| 1s | CAT129 authorized cooperative UAS | Replay → Core | Observation |
| 2s | CAT129 unknown cooperative UAS | Replay → Core | Observation |
| 3s | CAT129 unauthorized UAS | Replay → Core | Observation |
| 4s | CAT015 non-cooperative track (4660) | Replay → Core | Observation |
| 5s | CAT063 sensor degraded | Replay → Core | Sensor status |
| 25s | RF bearing + TDOA fix | Replay | Stimulus |
| 30s | Acoustic corroboration | Replay | Stimulus |
| 39.5s | Fresh observation with velocity | Replay → Core | Observation |
| 40s | **Named operator authorization** | Replay | **Trigger** |
| ~40s | **Core publishes mission delegation** | **Core** | **Authority** |
| 50s | Comms loss injection | Replay | Stimulus |
| ~50s | **S1 executes lost-link continuation** | **S1 → Core** | **Evidence** |
| 60s | Comms recovery injection | Replay | Stimulus |
| ~60s | **S1 resumes normal execution** | **S1 → Core** | **Evidence** |
| 70s | Civilian aircraft conflict | Replay | Stimulus |
| ~70s | **Core issues safety abort** | **Core** | **Authority** |
| ~70s | **S1 reaches Aborted/SafeHold** | **S1 → Core** | **Evidence** |
| 90s | Scenario complete | Replay | Stimulus |

## Key Technical Details

### Track Freshness
- `MAX_TRACK_AGE_MS = 5000` (5 seconds)
- The observation at 39.5s must be within 5 seconds of the authorization at 40s
- Timestamps are set at publication time (not at function call time)

### Delegation Guard
- S1's `cuas-health-injector` evaluates the production delegation guard
- Lost-link continuation is bounded by the existing delegation authority
- No new authority is created during comms loss

### Safety Abort
- `safety.civilian_aircraft_conflict` → Core publishes `swarm.command.abort`
- S1 reaches `Aborted / SafeHold` state
- Final evidence preserves original delegation correlation

## Running the Demo

```bash
cd /Users/vincent/Work/BOD-CUAS

# Check prerequisites
./demo/golden/doctor.sh

# Run full demo (auto-exit on success)
GOLDEN_EXIT_AFTER_ACCEPTANCE=1 ./demo/golden/smoke.sh

# Or equivalently:
GOLDEN_EXIT_AFTER_ACCEPTANCE=1 ./demo/golden/run.sh
```

## Expected Output

```
=== Verifier results ===
  ✅ verify.log: PASS
  ✅ verify-origin.log: PASS
  ✅ verify-comm-denied.log: PASS

============================================
  ✅ BORDEAUX C-UAS GOLDEN DEMO: PASS
============================================
```

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| NATS TCP | 4222 | nats://127.0.0.1:4222 |
| NATS WebSocket | 9222 | ws://127.0.0.1:9222 |
| ATAK | 8080 | http://127.0.0.1:8080 |
| Furia Core | 3000 | http://127.0.0.1:3000 |
| S1 Sim Server | 3227 | http://127.0.0.1:3227 |
| Furia C2 | 4180 | http://127.0.0.1:4180 |

## Logs

All logs are written to `${TMPDIR}/furia-bod-golden/`:

```
nats.log           NATS server
dev-atak.log       ATAK dev server
core.log           Furia Core server
cuas.log           C-UAS Director (with RUST_LOG=debug)
s1.log             S1 simulation server
s1-health.log      C-UAS health injector
sapient.log        SAPIENT simulator
c2.log             Furia C2
replay.log         Deterministic replay
verify.log         Main acceptance verifier
verify-origin.log  Threat origin verifier
verify-comm-denied.log  Communications-denied continuation verifier
```

## Non-Claims

This demo:
- Uses **synthetic/representative** airport scenario data
- Uses **deterministic simulated** surveillance inputs
- Demonstrates **Core-owned** inference and **bounded non-lethal** response delegation
- Demonstrates **safety-policy** abort
- Does **not** claim: certified ATC integration, automatic runway closure authority, autonomous detect-to-defeat, real Bordeaux sensor coverage, legal authority for RF or kinetic effects, or production safety certification