# Bordeaux C-UAS ASTERIX Integration Profile

This profile defines how Furia exchanges cooperative UAS, non-cooperative detections,
fused tracks, crewed-aircraft traffic, and sensor health with airport/ANSP systems.
It is an integration profile, not a replacement for the EUROCONTROL category specifications.

## Correct category roles

| Category | Role in the Bordeaux demo | Direction |
|---|---|---|
| CAT-129 | Cooperative UAS identification reports, including UAS identity and position | ingest and optional publish |
| CAT-015 | Independent non-cooperative surveillance target reports | ingest and publish |
| CAT-016 | INCS sensor/configuration metadata paired with CAT-015; not a target-report stream | ingest and optional publish |
| CAT-062 | Fused SDPS/system tracks | ingest and publish |
| CAT-021 | ADS-B target reports for cooperative crewed aircraft | ingest |
| CAT-004 | Safety-net events when supplied by ATC/SDPS | ingest |
| CAT-063 | Sensor/SDPS status | ingest and optional publish |
| CAT-253 | User-specific remote monitoring/control information; use only under an agreed bilateral UAP | bilateral (optional) |

CAT-033 is not the ADS-B target-report category. The Bordeaux integration uses CAT-021 for ADS-B.

## Core decoder baseline

The current Core ingress boundary is deliberately edition-pinned and fail-closed:

- CAT-015 Edition 1.2: bounded non-cooperative target subset with explicit measurement and association references;
- CAT-016 Edition 1.0: bounded INCS configuration subset with Pair ID -> transmitter/receiver mappings;
- CAT-021 Edition 2.7: bounded cooperative crewed-aircraft subset;
- CAT-062 Edition 1.21: bounded system-track subset;
- CAT-063 Edition 1.7: bounded sensor/SDPS status subset;
- CAT-129 Edition 1.2: bounded cooperative UAS identity/state subset;
- CAT-253: no universal semantic decoder; accepted only through an explicit named bilateral profile gate.

Unsupported compound/profile-dependent fields are rejected rather than guessed. Raw validated records are hashed before normalization so rejected/accepted data can be reproduced and audited.

## Normalization boundary

ASTERIX decoding and edition-specific field handling belongs at the Core sensor-ingress boundary.
No ASTERIX category-specific fields cross into S1. Category adapters normalize surveillance data
into versioned Core observations and preserve immutable provenance:

```text
ASTERIX UDP/TCP feed
  -> bounded CAT/LEN framing
  -> edition/profile-pinned category decoder
  -> normalized observation/configuration + immutable provenance
  -> Core correlation/fusion/health/policy
  -> CopTrackV1 / protected volumes / MissionDelegationV1
```

Each normalized observation or configuration record preserves, where applicable:

- ASTERIX category and edition;
- bilateral profile name when required;
- SAC/SIC;
- source track number;
- CAT-015 measurement identifier: Pair ID + observation number;
- CAT-015 association measurement identifiers;
- CAT-016 Pair ID -> transmitter/receiver mapping;
- receive time and source time;
- position/altitude units and accuracy;
- cooperative/non-cooperative classification;
- raw-message digest for replay and audit.

## Cooperative UAS: CAT-129

CAT-129 reports identify and track cooperative UAS or Remote-ID-derived UAS records.
**Identity does not imply authorization.** Core correlates the reported identity against:

- airport and operator authorization lists;
- declared mission/flight windows;
- permitted volumes and altitude bands;
- registration/manufacturer/model/serial information when present;
- other sensor observations.

The decision result is one of:

```text
cooperative + authorized
cooperative + authorization unknown
cooperative + unauthorized
identity conflict / suspected spoofing
```

CAT-129 provenance retains its identity, SAC/SIC, edition, timing and raw-record digest. It must
not be assigned an INCS Pair ID unless a separate, explicitly defined correlation mechanism provides one.

## Non-cooperative surveillance: CAT-015 and CAT-016

CAT-015 carries INCS target reports. CAT-016 carries associated INCS configuration metadata.
Core preserves the standard traceability chain instead of flattening the two categories:

```text
CAT-015 I015/400 measurement identifier
  = Pair ID + observation number
        |
        v
CAT-016 I016/300 pair identification
  = Pair ID -> transmitter ID + receiver ID
```

CAT-015 I015/480 associations are retained as a bounded list of additional measurement references.
This allows one target report to retain multi-measurement provenance.

Core must not interpret CAT-016 as another target stream. It enriches CAT-015 provenance,
sensor geometry, configuration and health context.

## Fused tracks: CAT-062

CAT-062 is the preferred interface for exchanging fused system tracks with an airport SDPS,
ANSP, UTM/U-space component, or higher C2.

Inbound CAT-062 tracks remain externally owned and are correlated with local Core tracks.
Outbound CAT-062 publication requires an explicit interface agreement covering:

- category edition;
- UAP/profile and mandatory data items;
- track-number namespace;
- SAC/SIC allocation;
- coordinate/altitude datum;
- covariance/accuracy representation;
- update rate and latency;
- lifecycle events and deletion semantics.

## Crewed-aircraft protection: CAT-021

CAT-021 ADS-B traffic is ingested as cooperative crewed-aircraft surveillance. Core converts
current and predicted aircraft occupancy into moving protected volumes. Only the bounded local
subset relevant to an interceptor is delegated to S1.

```text
CAT-021 aircraft track
  -> Core trajectory prediction
  -> moving protected volume
  -> MissionDelegationV1 C-UAS constraints
  -> S1 guidance -> ORCA3D -> final command validation -> platform adapter
```

An interceptor mission is blocked, rerouted, held, or aborted when delegated safety constraints
cannot be satisfied.

## CAT-253 bilateral profiles

CAT-253 is not treated as a universal interoperable payload. Before a Bordeaux deployment enables it,
the integration partner must provide a versioned bilateral profile containing at minimum:

- profile name and edition;
- exact UAP/data-item layout;
- minimum/maximum record size;
- SAC/SIC location if the profile carries them;
- command/monitoring semantics;
- authority model and allowed directions;
- authentication/transport assumptions;
- replay/idempotency rules;
- test fixtures.

Core first applies the named CAT-253 profile gate. Only the matching provider adapter may then decode
profile-specific semantics. A CAT-253 record from an unknown or unnamed profile is rejected.

No `BOD-CUAS-v1` CAT-253 semantic UAP is claimed by this repository yet. That name must not be used
operationally until its field-level profile and fixtures are committed and agreed with the integration partner.

## Health and safety integration

- CAT-063 sensor status contributes to integration health and observation confidence.
- CAT-004 safety-net events are displayed and may trigger Core policy gates, but Furia does not fabricate ATC safety-net decisions.
- CAT-253 is enabled only for a named, agreed bilateral integration profile.

## Security

ASTERIX itself is not treated as an authenticated authority channel. Deployment must provide:

- network segmentation and allow-listed endpoints;
- source identity at the transport/tunnel layer;
- replay protection and sequence monitoring;
- raw-message hashing and immutable audit logs;
- schema/category/edition/profile allow lists;
- bounds checks before allocation or decoding;
- rejection of impossible coordinates, stale timestamps, and conflicting identity data.

Any experimental authentication wrapper or CAT-000 convention must remain outside the standard
category decoder and be explicitly negotiated with the integration partner.

## Bordeaux acceptance sequence

1. CAT-129 reports an identified inspection UAS.
2. Core authorization policy resolves it as authorized, unknown or unauthorized independently of CAT-129 identity.
3. CAT-015 reports a non-cooperative target approaching runway 05/23.
4. Its measurement Pair ID resolves through CAT-016 to the contributing transmitter/receiver pair.
5. Core fuses observations and publishes an internal threat track with source provenance.
6. CAT-021 reports a crewed aircraft on approach.
7. Core creates a moving protected volume and modifies/blocks the interceptor plan as required.
8. Core delegates a bounded C-UAS contract to S1.
9. S1 executes guidance -> ORCA3D -> final-command validation -> Antoine/MAVLink output boundary.
10. A degraded communications event causes only policy-permitted last-valid-contract continuation.
11. On reconnection, S1 returns execution evidence and assignment generation.
12. The fused non-cooperative track is available for an explicitly agreed CAT-062 publication profile.
13. CAT-063 degradation reduces source confidence and is visible in C2.

## Standards baseline

Deployment configuration records the exact editions/profiles in use. Current Core decoder targets are:

- CAT-129 Edition 1.2;
- CAT-015 Edition 1.2;
- CAT-016 Edition 1.0;
- CAT-062 Edition 1.21;
- CAT-021 Edition 2.7;
- CAT-063 Edition 1.7;
- CAT-253 only through an explicit bilateral profile.

Operational and performance requirements should be traced to ED-286 / DO-389 and ED-322 /
DO-403 where available to the programme. Future WG-115 interoperability requirements should be
incorporated through versioned profiles rather than hard-coded assumptions.
