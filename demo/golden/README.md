# Bordeaux Golden Demo

This directory is the deterministic executable acceptance path for the Furia ecosystem.

## Goal

From sibling checkouts of `BOD-CUAS`, `furia-core`, `furia-ui`, `furia-c2`, and `S1`:

```bash
cd BOD-CUAS
bash demo/golden/smoke.sh
```

That one command boots the real NATS JetStream backbone, the Core airport/C-UAS services, S1 simulation/runtime boundary, and the Furia C2 host; runs the deterministic Bordeaux ASTERIX/operational replay; verifies the live authority, execution-evidence, and safety-abort chain in causal order; checks post-scenario process liveness; then shuts everything down and exits successfully only after acceptance passes.

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

The runner builds and starts:

- NATS JetStream TCP on `:4222` and WebSocket on `:9222`
- `dev-atak-server` on `:8080`
- `furia-core-server` on `:3000`
- `counter-uas-director` as a NATS-only service
- `sapient-simulator`
- `s1-sim-server` on `:3227`
- `furia-c2` Vite host on `:5173`

All child processes are terminated together on exit or Ctrl-C.

## Live smoke acceptance

The harness injects only canonical scenario stimuli. It never fabricates S1 delegation, execution evidence, or abort commands. The verifier requires the real runtime chain:

```text
ASTERIX surveillance
      ↓
Core protected-volume risk + incident state
      ↓
named operator authorization
      ↓
furia.s1.mission-delegation
      ↓
Core read-only cuas.mission.delegation projection
      ↓
S1 execution progress + Core-admitted cuas.execution.evidence
      ↓
swarm.fsm.state = ExecutingOpord
      ↓
civilian-aircraft safety conflict
      ↓
Core swarm.command.abort
      ↓
S1 swarm.fsm.state = Aborted / SafeHold
      ↓
swarm.command.result.abort = executed
```

The smoke test also verifies that the deterministic replay completed successfully and that Core, C-UAS Director, S1, SAPIENT, C2, and the dev ATAK service are still alive after the scenario.

## Acceptance story

1. Airport surveillance starts with normal cooperative traffic.
2. An authorized UAS is identified and not escalated.
3. A non-cooperative UAS is detected and normalized into the operational stream.
4. Protected-volume prediction raises runway risk and incident state; sensor degradation remains visible rather than silently clearing the threat.
5. Operator explicitly authorizes a bounded non-lethal response.
6. Core emits `MissionDelegationV1`; S1 admits it and emits correlated execution evidence.
7. Core admits/normalizes that evidence and exposes the read-only operator plane consumed by C2.
8. A civilian-aircraft conflict triggers `BOD-RWY-FRATRICIDE-003` through the canonical safety path.
9. S1 enters `Aborted` / `SafeHold` and reports an executed abort result.
10. Acceptance passes only when the required events appear in a causally valid order.

## Definition of done

A fresh machine with the five sibling repositories can run:

```bash
bash demo/golden/smoke.sh
```

and receive:

```text
SMOKE RESULT: PASS
```

without manually editing configuration, publishing NATS messages, starting services, or cleaning up processes.

The authoritative contracts remain in `furia-core`; this directory owns only the Bordeaux scenario fixtures, orchestration, and acceptance timeline.
