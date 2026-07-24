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

## Presenter Script

### Setup (2 min)

```
Presenter says:
  "This is the Bordeaux Airport C-UAS golden demo. It proves the full
   multi-repository runtime chain from surveillance through Core delegation,
   S1 execution, communications-loss continuation, civilian safety abort,
   and C2 visualization."

Actions:
  1. Open terminal at /Users/vincent/Work/BOD-CUAS
  2. Run: make clean && make demo
  3. Wait for "✅ BORDEAUX C-UAS GOLDEN DEMO: PASS"
  4. Open browser to http://127.0.0.1:4180/?auto=cuas
     (The C2 auto-launches the C-UAS scenario — no click needed)
```

### Walkthrough (5 min)

```
Presenter says (while demo runs):
  "The demo injects deterministic surveillance stimuli — ASTERIX CAT015/129
   tracks, RF bearings, acoustic data — into the Core. Core owns all
   authority: it fuses observations, applies authorization policy, and
   waits for a named operator command."

  [~5s] "A non-cooperative track appears on the runway approach.
          Sensor degradation is reported."

  [~25s] "RF sensors triangulate the threat origin. Acoustic sensors
           corroborate. Core infers a probable launch zone."

  [~44s] "⚠ OPERATOR DECISION REQUIRED — the C2 shows a modal asking
           the operator to authorize interception. The operator reviews
           the threat: track 4660, runway 23 approach, non-lethal track
           & shadow only. They click AUTHORIZE INTERCEPTION."

  [~44s] "Core creates a bounded mission delegation — 300 seconds of
           authority, non-lethal track-and-shadow only."

  [~54s] "Communications are lost. S1 continues within the existing
           bounded delegation — lost-link continuation, not new authority."

  [~64s] "Communications recover. S1 returns to normal execution."

  [~74s] "⚠ CIVILIAN CONFLICT — a civilian aircraft (AFR762) conflicts
           with the response volume. Core issues a safety abort.
           S1 reaches Aborted/SafeHold."

  [~94s] "Scenario complete. All services remain alive."
```

### Verification (1 min)

```
Presenter says:
  "Three independent verifiers confirm the causal chain:"

Actions:
  - Point to terminal output:
    ✅ verify.log: PASS          (delegation < abort ordering)
    ✅ verify-origin.log: PASS   (delegation payload validated)
    ✅ verify-comm-denied.log: PASS (lost-link + recovery proven)
```

### C2 Visual (2 min)

```
Presenter says:
  "Open http://127.0.0.1:4180/?auto=cuas in a browser. The C2 auto-launches
   the C-UAS scenario. The right sidebar shows the C-UAS status panel."

Actions:
  - Point to the C-UAS info panel (right sidebar):
    • Status bar: ACTIVE/NORMAL → ACTIVE/LOST LINK → ABORTED/SAFE HOLD
    • COMMS STATUS: green/yellow/red indicator
    • Threat track card: track ID, authority mode, authorization ID
    • Bounded authority countdown bar with seconds remaining
    • Degraded mode indicator + rejection reason
    • ⚠ SAFETY CONFLICT card (appears at ~74s): flight ID, track ID, policy
    • Real-time execution timeline
    • ✓ SCENARIO COMPLETE summary card (appears at ~94s): metrics

  - Point to the map:
    • Bordeaux LFBD operational map with OSM tiles
    • Protected volume zones (LFBD PROTECTED VOLUME, CIVIL APPROACH CORRIDOR)
    • S1 AUTHORITY ENVELOPE zone
    • Track symbols color-coded by affiliation (hostile/friend/unknown/suspect)
    • ⚠ CIVILIAN CONFLICT — ABORT banner (appears at ~74s)
    • BOUNDED AUTHORITY badge (appears after delegation)
```

## Running the Demo

```bash
cd /Users/vincent/Work/BOD-CUAS

# Quick run (assumes binaries already built)
SKIP_BUILD=1 make demo

# Full run (builds everything first)
make demo

# Check prerequisites
make doctor

# Clean state
make clean
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
cuas.log           C-UAS Director (RUST_LOG=debug)
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
- Does **not** claim: certified ATC integration, automatic runway closure authority, autonomous detect-to-defeat, real Bordeaux sensor coverage, legal authority for RF or kinetic effects, or production safety certification", "file_path": "/Users/vincent/Work/BOD-CUAS/demo/golden/PRESENTER.md"}