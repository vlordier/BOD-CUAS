# Bordeaux Golden Demo

This directory is the deterministic executable acceptance path for the Furia ecosystem.

## Goal

From sibling checkouts of `BOD-CUAS`, `furia-core`, `furia-ui`, `furia-c2`, and `S1`:

```bash
cd BOD-CUAS
bash demo/golden/run.sh
```

The first milestone boots the real Core C-UAS services and the real Furia C2 host. The scenario timeline is fixed by `timeline.yaml` so subsequent integration work has one stable target rather than ad-hoc manual demos.

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

`run.sh` builds and starts:

- `dev-atak-server` on `:8080`
- `furia-core-server` on `:3000`
- `counter-uas-director` as a NATS-only service
- `sapient-simulator` as a NATS-connected simulator
- `furia-c2` Vite host on `:4180`

All child processes are terminated together on Ctrl-C.

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

## Definition of done

The demo is complete when a fresh machine can run one command and observe the deterministic authority chain without manually editing configs or publishing messages. `run.sh` exits nonzero if any verifier fails.

The authoritative contracts remain in `furia-core`; this directory owns only the Bordeaux scenario fixtures, orchestration, and acceptance timeline.

## C2 operational context read model

`replay.py` additionally emits a versioned `cuas.operational.context` read model.
It is deliberately **additive and C2-only**: Core neither consumes it nor derives
authority from it. The existing `surveillance.observation`, operator authorization,
S1-health and civilian-conflict inputs remain the authoritative demo stimuli.

The context updates at surveillance, assessment, bounded execution, lost-link
continuation and safety-abort transitions. It supplies rendering-only airport
context, fused source summary, confidence, data freshness, predicted entry,
bounded authority constraints and the civil-flight safety rationale. Its typed
fixture and representative payload are in `operational-context.json`.

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
