# BOD-CUAS resilience scenarios

This directory contains a dependency-free, deterministic scenario DSL and
coverage audit for BOD-CUAS resilience testing. It does not modify the golden
replay or connect to live systems.

## Current audit

The manifest records two verified capabilities:

- `bod-cuas-golden`: deterministic surveillance, assessment, named operator
  authorization, bounded execution, lost-link continuation, civilian-conflict
  safety inhibition, correlated S1 safe-hold, and recovery. Its evidence is
  checked by the three golden verifiers plus contract fixture tests.
- `live-context-display-only`: provenance, freshness, and safe authority
  boundaries for weather, airport-operations, U-space, and EO/IR context.
  These feeds are explicitly display-only and cannot create authority.

The five resilience fixtures are implemented as versioned actor/sensor/fault
documents and are expanded by the isolated fault replayer into observations.
They are reported as `partial`: the deterministic fixture, loader, and
side-effect-free expansion are tested, while live sensor/ATC/authority
integrations are intentionally outside this package.

This distinction is intentional: synthetic scenario evidence is not treated as
airport, ATC, or safety authority evidence.

## Generate the report

From `/Users/vincent/Work/BOD-CUAS`:

```sh
python3 demo/resilience/coverage.py --format markdown
python3 demo/resilience/coverage.py --format json --output /tmp/bod-cuas-coverage.json
python3 demo/resilience/coverage.py --check
```

`--check` fails closed when any manifest entry lacks:

- at least one expected outcome;
- an authority boundary with owner, allowed actions, prohibited actions, and
  required evidence;
- declared inputs and safety states; or
- valid verification status.

The checker validates the manifest structure. The five DSL entries remain
`verification_status: partial` until a real simulator and executable
scenario-specific verifier are added.

## Extend the audit

When a new simulator is added, add one manifest entry with its real source,
inputs, exercised states, expected outcomes, authority boundary, and verifier
paths. Mark it `partial` until every expected outcome has an executable
assertion, then mark it `verified` and document the evidence basis. Keep
training, context-only, and operational authority boundaries explicit.
