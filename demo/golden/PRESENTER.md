# Bordeaux-Mérignac C-UAS Golden Demo — Presenter Runbook

## Objective

Demonstrate a credible airport-safety C-UAS workflow in which Furia:

1. ingests heterogeneous surveillance through bounded ASTERIX interfaces;
2. distinguishes authorized, authorization-unknown, unauthorized, non-cooperative, and crewed tracks;
3. predicts protected-volume risk and exposes affected runway/sector and 30/60/120 s horizons;
4. keeps sensor degradation visible without clearing an existing threat;
5. requires explicit named human authority before any bounded response is delegated;
6. shows exactly what Core delegated and what S1 is executing;
7. prioritizes civilian-flight safety and aborts/holds safely on conflict;
8. leaves an auditable evidence trail.

The demo is intentionally non-lethal. The response shown is bounded track/shadow/intercept execution under explicit authority, with civilian-safety abort precedence.

## Preflight

Run:

```bash
./demo/golden/run.sh --doctor
```

All checks must be green. In particular:

- `furia-core`, `furia-ui`, `furia-c2`, `S1`, and `BOD-CUAS` are sibling repositories;
- `config/cuas-authorizations.yaml` is present;
- `demo/golden/protected-volumes.yaml` and ASTERIX fixtures are present;
- NATS can expose TCP `4222` and WebSocket `9222`;
- ports `3000`, `3227`, `5173`, `4222`, and `9222` are available.

Start the complete stack with:

```bash
./demo/golden/run.sh
```

Open C2 at `http://127.0.0.1:5173` and select the C-UAS/Bordeaux workspace if it is not already active.

## What the audience should see

### 1. Establish trust in the air picture

Point out that the map is centered on Bordeaux-Mérignac, not a generic simulation area.

Visible protected zones should include:

- runway 05/23 protection;
- RWY23 approach;
- RWY05 approach;
- apron-critical area.

Explain that surveillance is normalized in Core and the UI does not parse ASTERIX directly.

Expected track classes during the first phase:

- authorized cooperative inspection UAS;
- cooperative UAS with authorization unknown;
- known-but-expired cooperative UAS shown unauthorized;
- non-cooperative runway track;
- sensor health / INCS provenance indicators.

Do not describe authorization-unknown as hostile.

### 2. Show the runway-risk prediction

At the runway-incursion prediction phase, the tactical overlay must show:

- `CREDIBLE THREAT` for the non-cooperative track;
- affected runway/sector `05/23`;
- standard 30/60/120 s horizon display;
- predicted entry inside the 60 s and 120 s horizons;
- recommendation `PROTECT VOLUME`;
- confidence value.

Explain that this is decision support only. It does not itself authorize mitigation.

### 3. Degrade a sensor without losing the threat

The CAT063 degraded sensor event must produce an obvious operator indication:

- sensor badge changes to degraded/warning;
- risk overlay shows `SENSOR COVERAGE DEGRADED`;
- the existing credible threat remains present.

Message to audience: loss/degradation of one sensor reduces confidence/coverage; it never automatically clears a previously established threat.

### 4. Show explicit authority separation

Before operator authorization, the incident panel must show:

- operator acknowledgement required;
- mitigation not authorized;
- no named decision authority granted.

After the explicit named authorization input, show that Core creates the bounded S1 delegation.

The operator must be able to see:

- mission and revision;
- delegation mode;
- authorization identifier;
- target identifier;
- maximum track age;
- lost-link policy;
- remaining authority time.

Message to audience: Core owns global authority and mission allocation; S1 receives only a bounded local contract.

### 5. Show execution evidence, not just a command

The S1 execution section must display admitted Core-projected evidence:

- execution state;
- degraded mode;
- remaining contract authority;
- target-track age;
- rejection reason when present;
- active constraints when available.

Explain that Core admits evidence only when contract, mission, revision and monotonic ordering match the authoritative delegation.

### 6. Demonstrate civilian-flight-safety precedence

When `AFR762` creates the civilian-aircraft conflict:

- Core emits the canonical safety abort;
- S1 stops the active scenario;
- the FSM moves to `Aborted` / `SafeHold`;
- abort result is `executed`.

This is the strongest safety moment in the demo: civilian flight safety overrides the ongoing response.

### 7. Close with evidence and replayability

Show the acceptance result and logs under `${TMPDIR:-/tmp}/furia-bod-golden`.

The closed-loop verifier must prove all of the following before printing PASS:

- Core protected-volume risk event observed;
- incident event requires acknowledgement and is not self-authorized;
- sensor degradation remains visible;
- Core emits a valid bounded S1 delegation;
- Core projects the same delegation read-only to C2;
- S1 accepts the delegation;
- Core admits S1 execution evidence;
- executing FSM is observed;
- civilian-safety abort command is emitted;
- S1 reports abort executed;
- FSM reaches `Aborted` / `SafeHold`.

## Presenter framing

Lead with airport operations, not “drone combat.”

Recommended framing:

> “Furia creates a single low-altitude operational picture, distinguishes what is authorized from what is merely cooperative, predicts which runway or protected volume is at risk, keeps degraded sensors explicit, and separates decision authority from local autonomous execution. The important part is not just detecting a drone — it is making a defensible airport decision quickly, showing exactly why, and failing safe when civil aviation safety conflicts with the response.”

## Do not claim

Do not claim that this demo proves:

- certified ATC integration;
- automatic runway closure authority;
- autonomous detect-to-defeat;
- real-world sensor coverage performance at Bordeaux-Mérignac;
- legal authorization for RF effects or kinetic mitigation;
- production safety certification.

Those require airport/ANSP integration, operational approvals, deployment-specific sensors, exercises and certification evidence beyond this software golden path.
