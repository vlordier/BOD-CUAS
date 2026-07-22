# Bordeaux Golden Demo

This directory is the deterministic executable acceptance path for the Furia ecosystem.

## Goal

From sibling checkouts of `BOD-CUAS`, `furia-core`, `furia-ui`, `furia-c2`, and `S1`:

```bash
cd BOD-CUAS
bash demo/golden/smoke.sh
```

That single command boots the real NATS JetStream backbone, Core C-UAS services, S1 simulation/runtime boundary, and Furia C2 host; replays the deterministic Bordeaux ASTERIX/operational scenario; verifies the live command/evidence/abort chain in causal order; checks that the replay and long-running services stayed alive; then shuts everything down and exits `0` only on acceptance success.

For an interactive demo that remains running after acceptance:

```bash
bash demo/golden/run.sh
```

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

## Commands

```bash
bash demo/golden/doctor.sh
bash demo/golden/smoke.sh
bash demo/golden/run.sh
```

`run.sh` builds and starts:

- NATS JetStream on `:4222`
- `dev-atak-server` on `:8080`
- `furia-core-server` on `:3000`
- `counter-uas-director` on `:3475`
- `sapient-simulator`
- `s1-sim-server` on `:3227`
- `furia-c2` Vite host on `:5173`

All child processes are terminated together on exit or Ctrl-C.

## Smoke acceptance chain

The live verifier requires the real subjects and validates their causal relationships:

```text
ASTERIX + named operator authorization
          ↓
furia.s1.mission-delegation
          ↓
cuas.mission.delegation
          ↓
furia.s1.execution-progress
          ↓
cuas.execution.evidence
          ↓
swarm.fsm.state = ExecutingOpord
          ↓
safety.civilian_aircraft_conflict
          ↓
swarm.command.abort
          ↓
swarm.fsm.state = Aborted / SafeHold
          ↓
swarm.command.result.abort = executed
```

The harness never publishes S1 delegation, execution evidence, or abort commands directly. Those must be produced by the authoritative runtime path.

## Acceptance story

1. Airport surveillance starts with normal cooperative traffic.
2. An authorized UAS is identified and not escalated.
3. A non-cooperative UAS is detected and normalized into the operational stream.
4. Predicted runway incursion raises threat state.
5. Core resolves an S1 swarm capability and produces a bounded candidate intercept plan.
6. Operator explicitly authorizes the consequential action.
7. Core delegates through `MissionDelegationV1`; S1 admits it and emits correlated execution evidence.
8. Core admits/normalizes that evidence and exposes the read-only operator execution plane used by C2.
9. A civilian-aircraft conflict triggers `BOD-RWY-FRATRICIDE-003` and the canonical abort path.
10. S1 enters `Aborted` / `SafeHold`, publishes an executed abort result, and the smoke verifier accepts only the correctly ordered chain.

## Definition of done

A fresh machine with the five sibling repositories can run:

```bash
bash demo/golden/smoke.sh
```

and receive `SMOKE RESULT: PASS` without manually editing configs, publishing NATS messages, starting services, or cleaning up processes.

The authoritative contracts remain in `furia-core`; this directory owns only the Bordeaux scenario fixtures, orchestration, and acceptance timeline.
