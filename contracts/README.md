# BOD-CUAS contract fixtures

These files are example provider and operational-event payloads for the Bordeaux-Merignac C-UAS scenario.

The authoritative schemas live in `vlordier/furia-core/docs/contracts`:

- `provider-capabilities.schema.json`
- `operational-events.schema.json`

BOD-CUAS does not own or fork those schemas. It supplies scenario-specific fixtures that must remain valid against the Core versions.

Integration rule:

`BOD-CUAS -> furia-core provider boundary -> furia-c2 OperationalEventStream -> @furia/ui`

## Airport-pack boundary

Airport-specific identity, geodata, sensor placements, sectors and scenario
entrypoints are separated behind the generic airport-pack manifest described in
[`airport-packs.md`](./airport-packs.md). The LFBD fixture lives at
[`demo/golden/airport-packs/lfbd/manifest.json`](../demo/golden/airport-packs/lfbd/manifest.json).
Run `make airport-pack-check` to validate its references and cross-component
identifiers. This manifest is owned by BOD-CUAS and does not move generic Core
or UI primitives into this repository.

UI code must not import BOD-CUAS scenario implementation details directly.

## Coverage and 3D boundary

The generic spatial models now live in Core's `furia-coverage-model` crate:

- 3D points and trajectories;
- sensor and effector capability models;
- safety volumes and weather inputs;
- version-independent coverage samples and data sufficiency.

BOD-CUAS owns only the airport/scenario adapter: LFBD geometry, provider
configuration, synthetic data, and policy fixtures. It must not duplicate the
generic model or embed LFBD defaults in shared UI primitives. The UI receives
an operational world profile and a normalized projection through `furia-c2`.

The explicit inventory of that ownership is [`lfbd-demo-ownership.json`](./lfbd-demo-ownership.json).
Run `make ownership-check` to verify that every declared profile, scenario,
fixture and geospatial asset exists, that airport-pack references remain
inside this repository, and that the absence of LFBD Storybook stories is
intentional rather than accidental.

The runtime profile is [`../demo/golden/lfbd-operator-profile.json`](../demo/golden/lfbd-operator-profile.json).
`furia-c2` consumes it through the `@furia/airport-profile` adapter alias during the local golden build. This keeps
airport-specific coordinates, replay symbols and asset URLs in BOD-CUAS while the host remains responsible only for
normalisation and composition.
