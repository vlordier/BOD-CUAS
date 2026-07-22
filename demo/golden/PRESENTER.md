# Bordeaux-Mérignac C-UAS Golden Demo — Presenter Runbook

## Objective

Demonstrate a credible airport-safety C-UAS workflow in which Furia:

1. ingests heterogeneous surveillance through bounded ASTERIX interfaces;
2. distinguishes authorized, authorization-unknown, unauthorized, non-cooperative, and crewed tracks;
3. estimates likely launch origin and controller/emitter location from independent evidence while preserving uncertainty;
4. predicts protected-volume risk and exposes affected runway/sector and 30/60/120 s horizons;
5. keeps sensor degradation visible without clearing an existing threat;
6. requires explicit named human authority before any bounded response is delegated;
7. shows exactly what Core delegated and what S1 is executing;
8. proves bounded continuation during temporary communications loss, followed by recovery without creating new authority;
9. prioritizes civilian-flight safety and aborts/holds safely on conflict;
10. leaves an auditable, correlated evidence trail through final SafeHold.

The demo is intentionally non-lethal. The response shown is bounded track/shadow/intercept execution under explicit authority, with civilian-safety abort precedence.

## Preflight

From `BOD-CUAS`, run:

```bash
./demo/golden/run.sh --doctor
```

All checks must be green. In particular:

- `furia-core`, `furia-ui`, `furia-c2`, `S1`, and `BOD-CUAS` are sibling Git checkouts;
- the private local `@furia/ui` dependency and C2 lockfile are present;
- the S1 `cuas-health-injector` source is present;
- `config/cuas-authorizations.yaml`, protected volumes, ASTERIX fixtures, and threat-origin profile are present;
- NATS can expose TCP `4222` and WebSocket `9222`;
- ports `8080`, `3000`, `3227`, `5173`, `4222`, and `9222` are available.

For a pass/fail rehearsal, run:

```bash
./demo/golden/smoke.sh
```

Success is only when the script exits `0` after printing:

```text
SMOKE RESULT: PASS
```

For the live interactive presentation, run:

```bash
./demo/golden/run.sh
```

Open C2 at `http://127.0.0.1:5173`. The C-UAS/Bordeaux workspace should become active automatically; select it manually only if needed.

## What the audience should see

### 1. Establish trust in the air picture

Point out that the map is centered on Bordeaux-Mérignac, not a generic simulation area.

Visible protected zones include:

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
- crewed aviation when present;
- sensor-health and INCS provenance indicators.

Do not describe authorization-unknown as hostile.

### 2. Explain where the threat likely came from

The demo injects synthetic sensor observations, not simulator truth, using:

- distributed RF direction-finding bearings;
- RF TDOA fixes;
- acoustic bearing corroboration;
- canonical surveillance-track history/back-projection.

Core owns the inference and publishes separate concepts for:

- likely launch-origin hypotheses;
- controller/RF-emitter localization.

The tactical operator view should show:

- primary launch hypothesis and probability;
- alternative hypotheses when present;
- controller/emitter identifier;
- uncertainty dimensions and confidence;
- localization methods such as AOA/TDOA/fused;
- moving-emitter indication when supported by successive fixes.

Emphasize that uncertainty is preserved. Do not present the inferred launch point or controller location as an exact truth coordinate.

### 3. Show the runway-risk prediction

At the runway-incursion prediction phase, the tactical overlay must show:

- `CREDIBLE THREAT` for the non-cooperative track;
- affected runway/sector `05/23`;
- standard 30/60/120 s horizon display;
- predicted entry inside the 60 s and 120 s horizons;
- recommendation `PROTECT VOLUME`;
- confidence value.

Explain that the runway-incursion prediction is an upstream safety stimulus in this golden path; Core turns it into typed protected-volume risk and incident decision support. Do not claim this demo alone validates a certified airport trajectory-prediction system.

### 4. Degrade a sensor without losing the threat

The CAT063 degraded-sensor event must produce an obvious operator indication:

- sensor badge changes to degraded/warning;
- risk overlay shows `SENSOR COVERAGE DEGRADED`;
- the existing credible threat remains present.

Message to audience: loss/degradation of one sensor reduces coverage; it never automatically clears a previously established threat.

### 5. Show explicit authority separation

Before operator authorization, the incident panel must show:

- operator acknowledgement required;
- mitigation not authorized;
- no named decision authority granted.

After the explicit named authorization input, show that Core creates the bounded S1 delegation.

The operator can see:

- mission and revision;
- delegation mode;
- authorization identifier;
- target identifier and track freshness bound;
- lost-link policy;
- remaining authority time.

Message to audience: Core owns global authority and mission allocation; S1 receives only a bounded local contract. Cooperative identity alone never grants authorization.

### 6. Show execution evidence, not just a command

The S1 execution section and execution timeline display Core-admitted evidence:

- accepted/active execution state;
- degraded mode;
- remaining contract authority;
- target-track age;
- rejection reason when present;
- active constraints when available;
- mission/contract correlation and revision continuity.

Explain that Core admits evidence only when it matches the authoritative delegation and ordering rules. Exact retransmissions are idempotent; stale/conflicting evidence is rejected.

### 7. Demonstrate bounded comm-denied continuation

At the communications-loss step, the replay injects only a simulation health fact on `s1.sim.execution-health`.

The S1 simulation health adapter runs the real delegation guard. The operator timeline must then show Core-admitted evidence equivalent to:

```text
ACTIVE · LOST LINK CONTINUATION
```

with positive remaining contract authority and no rejection reason.

Then communications recover. A later correlated evidence event must return to:

```text
ACTIVE · NORMAL
```

Message to audience: loss of communications does not create authority. Continuation exists only inside the previously delegated time/space/safety envelope; recovery returns to normal under the same contract.

### 8. Demonstrate civilian-flight-safety precedence

When `AFR762` creates the civilian-aircraft conflict:

- Core emits the canonical safety abort;
- S1 stops the active response;
- final S1 evidence remains correlated to the original delegation;
- final evidence reports `state=aborted` and `degraded_mode=safety_hold`;
- the FSM moves to `Aborted` / `SafeHold`;
- abort result is `executed` after the final evidence packet.

This is the strongest safety moment in the demo: civilian flight safety overrides the ongoing response.

### 9. Close with evidence and replayability

Show the acceptance result and logs under `${TMPDIR:-/tmp}/furia-bod-golden`.

The golden verifier must prove, in causal order:

- Core-owned emitter localization and threat-origin inference before delegation;
- protected-volume risk and incident decision-support events;
- sensor degradation remains visible;
- incident requires acknowledgement and is not self-authorized;
- Core emits a valid bounded S1 delegation and read-only operator projection;
- S1 accepts and executes the delegation;
- Core admits correlated execution evidence;
- bounded lost-link continuation occurs while authority remains valid;
- normal recovery follows the lost-link state;
- civilian-safety abort occurs only afterward;
- final correlated `Aborted/SafeHold` evidence precedes the abort result;
- FSM reaches `Aborted / SafeHold`;
- replay completes and all managed demo services remain alive.

## Presenter framing

Lead with airport operations, not “drone combat.”

Recommended framing:

> “Furia creates a single low-altitude operational picture, distinguishes what is authorized from what is merely cooperative, estimates where a threat likely originated without hiding uncertainty, predicts which runway or protected volume is at risk, and separates decision authority from bounded local autonomous execution. When communications degrade, authority does not expand; when civil aviation safety conflicts with the response, safety wins. Every transition is visible and correlated back to the original decision.”

## Do not claim

Do not claim that this demo proves:

- certified ATC/ANSP integration;
- automatic runway closure authority;
- autonomous detect-to-defeat;
- real-world sensor placement, coverage, probability of detection, or localization accuracy at Bordeaux-Mérignac;
- that synthetic RF/acoustic observations correspond to deployed airport sensors;
- exact controller/person identity from RF localization;
- legal authorization for RF effects or kinetic mitigation;
- production safety certification.

Those require deployment-specific sensors, airport/ANSP integration, legal/operational approvals, exercises, measurement campaigns, assurance evidence, and certification beyond this software golden path.
