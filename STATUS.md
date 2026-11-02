# Bordeaux Airport C-UAS Golden Demo — Status Report

> **Date:** 2026-07-23  
> **Branch:** `golden-demo-bordeaux` (BOD-CUAS), `golden-demo-observation-subscriber` (furia-core),  
> `golden-demo-cuas-health-injector` (S1), `golden-demo-script` (furia-c2)  
> **Status:** 🟡 Deterministic fixtures and contract checks pass; full cross-repository live acceptance remains a release gate

---

## Architecture

### Authority Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        REPLAY (stimuli only)                 │
│  scenario.status, surveillance.observation,                  │
│  operator.action.authorized, s1.sim.execution-health,        │
│  safety.civilian_aircraft_conflict                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ NATS
┌─────────────────────▼───────────────────────────────────────┐
│                    CORE (owns authority)                      │
│  • ASTERIX ingestion + normalization                         │
│  • Surveillance fusion + canonical state                     │
│  • Authorization policy (cooperative/non-cooperative)        │
│  • Mission delegation creation  ←─── operator.authorized     │
│  • Safety abort generation     ←─── civilian_aircraft_conflict│
│  • Publishes: furia.s1.mission-delegation, swarm.command.abort│
└──────┬──────────────────────┬───────────────────────────────┘
       │ NATS                 │ NATS
┌──────▼──────────────┐  ┌───▼───────────────────────────────┐
│   S1 (execution)     │  │   C2 (read-only display)          │
│  • Delegation guard  │  │  • Map with OSM tiles             │
│  • Lost-link cont.   │  │  • Track symbols + no-fly zones   │
│  • Safety hold       │  │  • CuasInfoPanel (right sidebar)  │
│  • Publishes:        │  │    - Threat track card            │
│    furia.s1.execution│  │    - Authority countdown          │
│    -evidence         │  │    - Degraded mode indicator      │
└──────────────────────┘  │    - Execution timeline           │
                          └──────────────────────────────────┘
```

### NATS Subjects

| Subject | Publisher | Consumer | Payload (snake_case) |
|---------|-----------|----------|---------------------|
| `surveillance.observation` | Replay | Core | `SurveillanceObservationEventV1` |
| `operator.action.authorized` | Replay | Core | `{action, track_id, operator, authorization_id, authorized}` |
| `operator.action.command` | Visible C2 training surface | S1 simulation gateway | `{command, mission_id, track_id, operator, authority_mode}` |
| `s1.sim.execution-health` | Replay | S1 injector | `{mission_id, comms_available, navigation_safe, authority_valid, observed_at_ms, track_observed_at_ms}` |
| `safety.civilian_aircraft_conflict` | Replay | Core | `{mission_id, flight_id, track_id, policy}` |
| `scenario.status` | Replay | Verifiers, C2 | `{id, state, tick, elapsed_sec}` |
| `furia.s1.mission-delegation` | Core | S1 injector, Verifiers, C2 | `MissionDelegationV1` |
| `furia.s1.execution-evidence` | S1 injector | Verifiers, C2 | `ExecutionEvidenceV1` |
| `furia.s1.command-ack` | S1 injector | C2 | `{command, mission_id, track_id, contract_id, state, reason, observed_at_ms}` |
| `swarm.command.abort` | Core | Verifiers, C2 | `{policy_id, track_id, mission_id, metadata: {flight_id}}` |
| `cuas.operational.context.core` | Core | C2 | Versioned observation-derived read model; no authority |
| `cuas.feed.provenance` | Live-context bridge / labelled simulator | C2 | External-context provenance; never authority |
| `environment.weather.observation` | Live-context bridge / labelled simulator | C2 integration boundary | Weather context only |

### Ports

| Service | Port | Protocol |
|---------|------|----------|
| NATS TCP | 4222 | nats://127.0.0.1:4222 |
| NATS WebSocket | 9222 | ws://127.0.0.1:9222 |
| ATAK dev server | 8080 | HTTP |
| Furia Core | 3000 | HTTP |
| S1 sim server | 3227 | HTTP |
| Furia C2 | 4180 | HTTP (Vite) |

---

## What's Done

### Deterministic Replay (`demo/golden/replay.py`)

- Publishes pre-normalized observations to `surveillance.observation` (bypasses ASTERIX decoding)
- Timestamps captured at **publication time** (not function-call time) via `emit_with_now()` / `emit_obs()`
- All three `emit`/`emit_with_now`/`emit_obs` functions share a single sleep/publish/PING core via `inject` callback
- Scenario timeline:
  - 0s: scenario.status (running)
  - 1-3s: CAT129 cooperative UAS (authorized, unknown, unauthorized)
  - 4s: CAT015 non-cooperative track 4660
  - 5s: CAT063 sensor degraded
  - 25-30s: RF bearings + TDOA + acoustic
  - 39.5s: Fresh observation with velocity (within 5s track-age window)
  - 40s: Operator authorization
  - 50s: Comms loss injection
  - 60s: Comms recovery injection
  - 70s: Civilian aircraft conflict
  - 90s: scenario.status (complete)

### Three Independent Verifiers

| Verifier | Subjects | Checks |
|----------|----------|--------|
| `verify.py` | `scenario.status`, `furia.s1.mission-delegation`, `swarm.command.abort` | Causal ordering (delegation < abort), payload field validation |
| `verify_origin.py` | `furia.s1.mission-delegation` | Delegation payload fields (`mission_id`, `correlation_id`) |
| `verify_comm_denied.py` | `furia.s1.mission-delegation`, `furia.s1.execution-evidence` | Lost-link continuation + normal recovery evidence |

All verifiers use `timeout` wrapper + `nats sub --count N` for reliable exit.

### C2 CuasInfoPanel (`furia-c2/src/views/CuasInfoPanel.tsx`)

- Raw WebSocket NATS client (no Node.js dependency — works in browser)
- Subscribes to `furia.s1.mission-delegation`, `furia.s1.command-ack`, `furia.s1.execution-evidence`, `swarm.command.abort`, `scenario.status`
- **Audio alerts** via Web Audio API: delegation (beep-beep), lost link (warning tone), safety abort (urgent triple-beep)
- **Comms status indicator**: green/yellow/red bar showing COMMS status
- **Safety conflict card**: red-bordered box with flight ID, track ID, policy when abort received
- **Post-demo summary**: green metrics card after scenario.complete (detection→delegation, delegation→abort, lost link duration, total duration)
- Displays:
  - Status bar (color-coded: green=active, yellow=lost link, red=aborted)
  - Threat track card (ID, mode, authorization, revision)
  - Bounded authority countdown bar (updates every 1s via `setInterval`)
  - Degraded mode indicator + rejection reason
  - Real-time execution timeline

### C2 Console View (`furia-c2/src/views/Console.tsx`)

- **Protected volume zones**: LFBD PROTECTED VOLUME, CIVIL APPROACH CORRIDOR, S1 AUTHORITY ENVELOPE rendered as `MapZone[]` overlays on the map
- **Safety conflict overlay**: red "⚠ CIVILIAN CONFLICT — ABORT" banner on the map when abort received, plus dynamic conflict zone
- **C-UAS symbology**: tracks color-coded by affiliation (hostile=4660, friend=7001, unknown=7002, suspect=7003)
- **Authority delegated indicator**: blue "BOUNDED AUTHORITY: INTERCEPT" badge on the map

### Service Orchestration (`demo/golden/run.sh`)

- `wait_http` for HTTP health endpoints
- `wait_tcp` for TCP port liveness
- `wait_log` for log-based readiness (C-UAS director, health injector)
- `SKIP_BUILD=1` to skip rebuild for iterative runs
- `GOLDEN_EXIT_AFTER_ACCEPTANCE=1` for auto-exit
- Cleanup kills all PIDs + removes NATS JetStream store

### Prerequisites Check (`demo/golden/doctor.sh`)

- Checks all 5 repos exist
- Checks `cargo`, `nats`, `nats-server`, `timeout`, `node`, `pnpm`, `python3`, `docker`
- Checks ports 4222, 9222, 8080, 3000, 3227, 4180 are free
- `lsof` fallback to `ss` on Linux

### Makefile (`BOD-CUAS/Makefile`)

- `make demo` / `make golden` — run full demo
- `make doctor` — check prerequisites
- `make clean` — kill processes + clean state (portable pkill patterns)

### CI Workflow (`.github/workflows/golden-contract.yml`)

- Checks out all 5 repos
- Builds Rust binaries, installs Node/pnpm deps
- Runs golden demo
- Generates acceptance report + log bundle

### Supporting Files

- `PRESENTER.md` — stakeholder walkthrough with timed script
- `acceptance_report.py` — machine-readable JSON report (1:1 check-to-log mapping)
- `bundle_logs.sh` — timestamped log archive
- `nats.conf` — NATS config with JetStream + WebSocket
- `threat-origin.yaml` — RF sensor positions + threat origin estimate
- `asterix_records.json` — 6 ASTERIX fixtures (CAT016, CAT129, CAT015, CAT063)

---

## Bugs Found & Fixed (6 passes)

| Pass | Bug | Fix |
|------|-----|-----|
| 1 | ASTERIX CAT015 decoder doesn't extract velocity → delegation rejected | Added `spawn_observation_subscriber` for pre-normalized observations |
| 1 | `nats sub --timeout` flag doesn't exist | Switched to `timeout` wrapper |
| 1 | C2 starts on port 4180, not 5173 | Updated `wait_http` to port 4180 |
| 1 | `futures::StreamExt` is private API in some crates | Changed to `futures_util::StreamExt` |
| 2 | Timestamps captured at function-call time, not publication time → track stale | Added `emit_with_now()` / `emit_obs()` that capture after sleep |
| 2 | Verifiers check camelCase fields but NATS uses snake_case | Fixed all verifiers to use `correlation_id`, `mission_id`, `policy_id` |
| 2 | Abort payload uses `policy_id` not `policy` | Fixed verify.py |
| 3 | `flight_id` nested under `metadata` in abort payload | Changed to `data.metadata?.flight_id` |
| 3 | Dead `delegation_time_ms` variable in replay.py | Removed |
| 3 | `bundle_logs.sh` / `acceptance_report.py` hardcoded macOS temp path | Changed to `${TMPDIR:-/tmp}` / `tempfile.gettempdir()` |
| 3 | `doctor.sh` `check_port` silently fails without `lsof` | Added `ss` fallback + warning |
| 4 | `nats sub --count N` hangs if expected messages never arrive | Added `timeout` wrapper as outer safety net |
| 4 | `sleep 2` after C-UAS director is blind wait | Replaced with `wait_log` |
| 4 | `sleep 3` after verifiers is unnecessary | Removed |
| 4 | `emit`/`emit_with_now`/`emit_obs` triplicated sleep/publish/PING logic | Refactored to single `emit` with `inject` callback |
| 4 | `remainingSec()`/`authorityPct()` call `Date.now()` on every render | Added `setInterval` ticker updating `now` signal |
| 4 | Edit injected literal `\n` string instead of real newline | Fixed with proper newline |
| 5 | `import { connect } from "nats"` uses NodeTransport → fails in browser | Replaced with raw `NatsWsClient` over browser WebSocket API |
| 5 | `make clean` pkill patterns use absolute workspace paths | Changed to `target/release/<binary>` |
| 6 | `sleep 2` after health injector is blind wait | Replaced with `wait_log` |

---

## What's Todo

### Completed gates

- [x] Fresh live replay with all three verifiers and correlated S1 safety-hold evidence
- [x] C2 reconnect, wire normalization, loading/error/empty-state behavior, and configurable WebSocket URL
- [x] Strict furia-ui lint, typecheck, contract tests, package validation, boundary checks, and bundle budgets
- [x] CI validation of furia-ui, furia-c2, Rust services, fixtures, and live golden replay
- [x] ATAK `auto`/`required`/`skip` modes with graceful degradation when port 8080 is occupied

### Production integration roadmap

- [ ] Replace training simulator sources with reviewed airport/ANSP, ADS-B, Remote-ID, and C-UAS sensor adapters
- [ ] Obtain and validate current LFBD static data under an approved AIRAC/source process
- [ ] Connect airport operations, USSP, and authority identity systems with explicit trust boundaries
- [ ] Run security, latency, accessibility, operator-console, and multi-display acceptance tests
- [ ] Remove legacy GridStack/GrapesJS compatibility adapters after downstream migration
- [ ] Pin immutable cross-repository refs and run the release-gate workflow
- [x] Include `VITE_NATS_WS_URL`, NATS, and ATAK runtime configuration in acceptance reports

---

## How to Run

```bash
# From BOD-CUAS root:
cd /Users/vincent/Work/BOD-CUAS

# Quick run (assumes binaries already built):
SKIP_BUILD=1 make demo

# Full run (builds everything):
make demo

# Check prerequisites:
make doctor

# Clean state:
make clean
```

## Expected Output

```
✅ verify.log: PASS
✅ verify-origin.log: PASS
✅ verify-comm-denied.log: PASS
✅ BORDEAUX C-UAS GOLDEN DEMO: PASS
```

## Latest local geospatial integration

- ✅ Bounded LFBD Bati3D package acquired from Bordeaux Métropole, integrity
  verified and indexed (1,260 200 m EPSG:3945 subtiles).
- ✅ LFBD airport-core subset prepared as 35 textured 3DS/FBX tiles with a
  reproducible manifest and explicit `historical_open_context` provenance.
- ✅ RealGazebo import completed through the normal UE 5.8 renderer: all 35
  tiles are installed under `Bati3D_2012` in the RealGazebo host project and
  every actor is tagged context-only. The reproducible importer deliberately
  refuses headless / `-NullRHI` use on this host because the renderer is part
  of the visual-context validation path.
- ⚠ Bati3D is a 2012 visual backdrop only. It is never current airport truth,
  obstacle authority, navigation data, or EO/IR evidence.

## C2 Visual

Open http://127.0.0.1:4180 in a browser. The C-UAS info panel appears in the right sidebar when the C-UAS scenario is active. It shows:

1. **Status bar** — color-coded execution state (green/yellow/red)
2. **Threat track card** — track ID, authority mode, authorization ID, plan revision
3. **Bounded authority countdown** — progress bar + seconds remaining
4. **Degraded mode indicator** — current degraded mode + rejection reason
5. **Execution timeline** — real-time event log (NATS connected → delegation → lost link → recovery → abort)
