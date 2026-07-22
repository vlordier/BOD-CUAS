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

## Commands

```bash
bash demo/golden/doctor.sh
bash demo/golden/run.sh
```

`run.sh` builds and starts:

- `dev-atak-server` on `:8080`
- `furia-core-server` on `:3000`
- `counter-uas-director` on `:3475`
- `sapient-simulator` on `:3476`
- `furia-c2` Vite host on `:5173`

All child processes are terminated together on Ctrl-C.

## Acceptance story

1. Airport surveillance starts with normal cooperative traffic.
2. An authorized UAS is identified and not escalated.
3. A non-cooperative UAS is detected and normalized into the operational stream.
4. Predicted runway incursion raises threat state.
5. Core resolves an S1 swarm capability and produces a candidate intercept plan.
6. Operator explicitly authorizes the consequential action.
7. S1 execution state is rendered through `OperationalEventStream`.
8. A civilian-aircraft conflict triggers `BOD-RWY-FRATRICIDE-003` and aborts/holds the swarm.
9. The operator timeline records detection, decision, authorization, execution, and abort evidence.

## Definition of done

The demo is complete when a fresh machine can run one command and observe the entire deterministic story without manually editing configs or publishing messages.

The authoritative contracts remain in `furia-core`; this directory owns only the Bordeaux scenario fixtures, orchestration, and acceptance timeline.
