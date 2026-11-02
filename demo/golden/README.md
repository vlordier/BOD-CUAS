# Bordeaux Golden Demo

This directory is the deterministic executable acceptance path for the Furia ecosystem.

## Goal

From sibling checkouts of `BOD-CUAS`, `furia-core`, `furia-ui`, `furia-c2`, and `S1`:

```bash
cd BOD-CUAS
bash demo/golden/run.sh
```

The first milestone boots the real Core C-UAS services and the real Furia C2 host. The scenario timeline is fixed by `timeline.yaml` so subsequent integration work has one stable target rather than ad-hoc manual demos.

The default run uses `furia-cuas` as the single canonical operational-projection
publisher. Core remains subscribed for compatibility context and decision
inputs, but does not publish a second canonical projection. Every external
projection carries `producer: furia-cuas-publisher`, which makes provenance
visible and allows duplicate-producer checks. The migration-only legacy mode is
explicit:

```bash
DEMO_CUAS_PROJECTION_MODE=compatibility bash demo/golden/run.sh
```

That mode must not be used as evidence that the extracted `furia-cuas` runtime
is canonical.

## Repository layout expected

```text
<root>/
  BOD-CUAS/
  furia-core/
  furia-ui/
  furia-c2/
  S1/
```

Set `FURIA_ROOT=/path/to/root` when using another layout.

## Cross-repository integration manifest

`integration-manifest.json` is the source-selection contract for CI. Each
dependency has a safe `development_ref` used by local development and ordinary
branch CI. After the participating changes are committed, set every
`pinned_ref` to its immutable 40-character lowercase Git SHA. CI automatically
prefers a pin when present; it never synthesizes one.

Validate the manifest locally:

```bash
python3 demo/golden/resolve_integration_manifest.py
python3 demo/golden/resolve_integration_manifest.py --require-pins
```

The second command is the release gate: it intentionally fails until all four
cross-repository revisions are pinned. Local sibling checkouts remain governed
by `FURIA_ROOT` and are not rewritten or checked out by this script.

## Commands

```bash
bash demo/golden/doctor.sh
bash demo/golden/run.sh
```

The doctor understands three NATS deployment modes. The default `auto` mode
checks that local ports are available. For a separately managed broker, run a
read-only connectivity check against its endpoint:

```bash
DEMO_NATS_MODE=external \
NATS_URL=nats://demo-nats.example:4222 \
VITE_NATS_WS_URL=wss://demo-nats.example/ws \
bash demo/golden/doctor.sh
```

External mode does not require a local `nats-server`, Docker, or ports 4222/
9222; it does require the `nats` CLI and verifies the broker with `nats rtt`.
For a local broker without the browser bridge, use headless mode:

```bash
DEMO_NATS_MODE=headless DEMO_NO_UI=1 bash demo/golden/doctor.sh
```

Headless mode checks only the local TCP port and deliberately does not treat
the WebSocket port as a prerequisite. These variables change diagnostics
only; they do not start, stop, or reconfigure a broker. The full `run.sh`
acceptance path deliberately owns a local broker, so it accepts `auto`/`local`
only; use `doctor.sh` for external or headless environments.

If the conventional local ports are occupied, isolate the run without editing
the configuration:

```bash
DEMO_NATS_TCP_PORT=4322 DEMO_NATS_WS_PORT=9322 bash demo/golden/run.sh
```

The runner generates a temporary NATS configuration with those ports and
passes the matching WebSocket endpoint to the C2.

All local service ports can be overridden independently with
`DEMO_CORE_PORT`, `DEMO_S1_PORT`, `DEMO_C2_PORT`, `DEMO_ATAK_PORT` and
`DEMO_SAPIENT_ADAPTER_PORT`. The doctor checks collisions before startup.
The configuration contract itself is covered by `make runtime-config-check`.
Set `DEMO_LOG_DIR=/path/to/logs` to retain runner logs in a known location;
otherwise they live below the platform temporary directory and are removed
from the active run on cleanup only by the operating system.

The replay metadata is defined in the versioned
`demo/golden/replay-profile.json` contract. Select another profile with
`DEMO_REPLAY_PROFILE=/path/profile.json`; individual fields can still be
overridden for a quick rehearsal with `DEMO_AIRPORT_ICAO`,
`DEMO_AIRPORT_NAME`, `DEMO_ACTIVE_RUNWAY`, `DEMO_AFFECTED_SECTOR`,
`DEMO_PROTECTED_VOLUME_ID` and `DEMO_SCENARIO_ID`. The LFBD coordinates and
authority fixtures remain the explicit Bordeaux scenario contract; changing
replay metadata alone does not claim that another airport has valid geometry
or operational integrations.

When `airport_pack_manifest` is present, the replay validates the referenced
pack and its identity component before publishing anything, including an ICAO
match. The doctor performs the same validation before any service starts. This
is the preferred form for a new airport profile.
Use `DEMO_SPEED=2` (or another positive multiplier) to accelerate a rehearsal;
the default remains real-time deterministic pacing.

`run.sh` builds and starts:

- `dev-atak-server` on `:8080` by default
- `furia-core-server` on `:3000` by default
- the C-UAS Decision & Coordination Node as the external `furia-cuas-publisher` NATS service
- `sapient-simulator` as a NATS-connected simulator
- `furia-c2` Vite host on `:4180` by default

All child processes are terminated together on Ctrl-C.

### SAPIENT transport paths

The default path keeps the deterministic simulator on the NATS boundary. To
exercise the real SAPIENT Protobuf ingress and the normalized handoff into the
canonical `furia-cuas` projection, run:

```bash
DEMO_SAPIENT_PATH=protobuf-adapter bash demo/golden/run.sh
```

This starts `sapient-adapter` on `:3395`, sends BSI Flex 335 v2.0 Protobuf
messages from `sapient-simulator`, and consumes only the adapter's normalized
detection subject in `furia-cuas`. The operator projection remains observation
only: a SAPIENT detection never grants effect authority or issues an action.
The direct NATS path remains available with `DEMO_SAPIENT_PATH=direct`.
The adapter port is configurable with `DEMO_SAPIENT_ADAPTER_PORT` when the
default is occupied.

## Acceptance story

1. Airport surveillance starts with normal cooperative traffic.
2. An authorized UAS is identified and not escalated.
3. A non-cooperative UAS is detected and normalized into the operational stream.
4. Predicted runway incursion raises threat state.
5. Core resolves an S1 swarm capability and produces a candidate intercept plan.
6. Operator explicitly authorizes the consequential action.
7. S1 lost-link continuation and normal-recovery evidence are observed.
8. A civilian-aircraft conflict triggers `BOD-RWY-FRATRICIDE-003`; Core issues an abort command.
9. The simulation-only S1 health injector accepts that command only when it matches its retained delegation, then publishes contract-correlated `aborted/safety_hold` evidence. The replay never fabricates that acknowledgement.

The acceptance verifier joins Core's abort to the delegation by `mission_id` and
delegated target `track_id`, then requires S1's safe-hold evidence to carry the
delegation `correlation_id` and the Core abort policy. This is deliberately
stronger than merely observing an abort and an unrelated execution event.

### Operator-led presentation mode

The unattended acceptance run retains an explicit deterministic authorization
fallback. For the polished presentation path, remove it and require the visible
operator action:

```bash
DEMO_AUTORIZE_FALLBACK=0 bash demo/golden/run.sh
```

In this mode the scenario remains at the decision gate until the operator
records authorization in C2; no hidden replay message grants it.

## Definition of done

The demo is complete when a fresh machine can run one command and observe the deterministic authority chain without manually editing configs or publishing messages. `run.sh` exits nonzero if any verifier fails.

The authoritative contracts remain in `furia-core`; this directory owns only the Bordeaux scenario fixtures, orchestration, and acceptance timeline.

## Resilience simulation pack

The isolated resilience pack exercises five additional deterministic failure
families without publishing authority or connecting to NATS:

- sensor disagreement and spoofed identity;
- stale tracks and observation loss;
- delegation expiry before acknowledgement;
- multi-threat and interceptor saturation; and
- runway-state changes with delayed operational acknowledgement.

Run the complete pack with:

```bash
make resilience-check
```

It validates the scenario DSL, expands each fixture through the fault replay,
asserts scenario-specific invariants, and generates machine-readable JSONL
when `demo/resilience/run_pack.py --output-dir <directory>` is used. These
scenarios are offline resilience evidence; they do not claim live sensor,
ATC, airport-operations, or authority integration.

## C2 operational context read model

`replay.py` additionally emits a versioned `cuas.operational.context.core` read model.
It is deliberately **additive and C2-only**: Core neither consumes it nor derives
authority from it. The existing `surveillance.observation`, operator authorization,
S1-health and civilian-conflict inputs remain the authoritative demo stimuli.

The context updates at surveillance, assessment, bounded execution, lost-link
continuation and safety-abort transitions. It supplies rendering-only airport
context, fused source summary, confidence, data freshness, predicted entry,
bounded authority constraints and the civil-flight safety rationale. Its typed
fixture and representative payload are in `operational-context.json`.

## Hybrid live-context mode

`../live-context/` provides the additive bridge used to put real receiver data
beside this deterministic incident. It normalizes a local ADS-B export as
CAT021 and a local Remote ID export as CAT129, retaining a raw-record digest
and publishing explicit `cuas.feed.provenance` status for the C2. It also has
strictly-labelled weather/airport/U-space context simulators for offline
rehearsals. None of these feeds can create authority, issue a command, or turn
the training replay into an airport-operational integration.

The standard demo also starts a continuous EO/IR metadata simulator. Its
moving target box, range and pointing information are consumed as
`video.metadata` and explicitly labelled `SIMULATED KLV`; it does not present
synthetic pixels as live imagery. Set `DEMO_CONTEXT_SIMULATORS=0` to omit it.

```bash
make live-context-check
python3 demo/live-context/context_bridge.py --config demo/live-context/context-sources.example.json
python3 demo/live-context/context_simulator.py
```

## LFBD demo geodata

`lfbd-demo-geodata.json` is the versioned map model for the replay. It carries
an LFBD reference point, illustrative runways, terminal/apron, approach and
departure corridors, policy-linked protected volumes, and RF/acoustic sensor
sites. Coordinates are WGS84 `[longitude, latitude]`.

It is explicitly hand-authored **demo geometry**, not a navigation product or
an airport-operational source. It must not be used for live aircraft movement,
airspace clearance, obstacle avoidance, sensor placement, or safety decisions.
`protected-volumes.yaml` remains the scenario policy fixture; matching IDs make
the visual layer traceable without making the visual layer authoritative.
