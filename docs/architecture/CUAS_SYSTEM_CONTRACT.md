# Furia C-UAS system contract — BOD-CUAS

## Role

`BOD-CUAS` is the Bordeaux-Mérignac reference scenario, integration configuration, threat/sensor fixture set, demo choreography and end-to-end acceptance-test repository.

It MUST NOT contain production policy or bypass canonical Core/S1 interfaces for convenience.

## Scenario responsibilities

- Define airport protected volumes, runways/approaches, operational sectors and scenario geometry.
- Define cooperative, unknown, unauthorized and hostile UAS scenarios without hard-coding classification outcomes into the harness.
- Provide sensor-feed fixtures for ASTERIX CAT-129, CAT-015/CAT-016, CAT-062 and other simulated feeds where applicable.
- Exercise sensor degradation, false/duplicate observations, stale tracks, comm loss and vehicle failures.
- Drive canonical inputs only; consume authoritative outputs only.
- Record golden event traces and expected safety/operational outcomes.

## Mandatory demo sequence

1. Normal airport operations with healthy sensor coverage.
2. Cooperative authorized drone appears and is correlated/cleared.
3. Non-cooperative track appears with uncertain identity.
4. Sensor fusion raises confidence while preserving provenance/uncertainty.
5. 120/60/30 s protected-volume risk escalates around an affected runway/sector.
6. Operator acknowledges incident; authority state is explicit.
7. Core delegates a bounded intercept/investigation mission to S1.
8. Swarm executes while C2/UI show live mission, safety and evidence state.
9. Inject degraded sensor or comms and demonstrate confidence degradation / bounded continuation.
10. Inject civilian-aircraft conflict; Core emits canonical abort; S1 enters SafeHold and returns evidence.
11. Reconnect/replay and prove no duplicate effect plus complete audit chain.

## Acceptance criteria

- No direct harness -> S1 operational command bypass.
- Every expected outcome is asserted from canonical events, not simulator internals.
- Golden traces are deterministic and CI replayable.
- Negative tests cover stale/malformed/conflicting commands and missing authority.
- Demo can run live or from recorded fixtures with the same C2/UI contract surface.
- End-to-end evidence links observation -> assessment -> decision -> authority -> command -> execution -> result.
