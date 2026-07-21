# Bordeaux C-UAS ASTERIX Integration Profile

This profile defines how Furia exchanges cooperative UAS, non-cooperative detections,
fused tracks, crewed-aircraft traffic, and sensor health with airport/ANSP systems.
It is an integration profile, not a replacement for the EUROCONTROL category specifications.

## Correct category roles

| Category | Role in the Bordeaux demo | Direction |
|---|---|---|
| CAT-129 | Cooperative UAS identification reports, including UAS identity and position | ingest and optional publish |
| CAT-015 | Independent non-cooperative surveillance target reports | ingest and publish |
| CAT-016 | INCS sensor/configuration metadata paired with CAT-015; not a target-report stream | ingest |
| CAT-062 | Fused SDPS/system tracks | ingest and publish |
| CAT-021 | ADS-B target reports for cooperative crewed aircraft | ingest |
| CAT-004 | Safety-net events when supplied by ATC/SDPS | ingest |
| CAT-063 | Sensor/SDPS status | ingest |
| CAT-253 | User-specific remote monitoring/control information; use only under an agreed bilateral UAP | optional |

CAT-033 is not the ADS-B target-report category. The Bordeaux integration uses CAT-021 for ADS-B.

## Normalization boundary

ASTERIX decoding and edition-specific field handling belongs in a `SensorAdapter` below
Furia Core. No ASTERIX category-specific fields cross into S1. The adapter normalizes all
surveillance messages into versioned Core observations and preserves provenance:

```text
ASTERIX UDP/TCP feed
  -> category/edition decoder
  -> source validation and timestamping
  -> SensorObservationV1 + SurveillanceSourceRefV1
  -> Core correlation/fusion
  -> CopTrackV1
```

Each normalized observation records:

- ASTERIX category and edition;
- SAC/SIC;
- source track number when available;
- CAT-129 Pair ID or CAT-015/CAT-016 association when available;
- receive time and source time;
- position/altitude units and accuracy;
- cooperative/non-cooperative classification;
- raw-message digest for replay and audit.

## Cooperative UAS: CAT-129

CAT-129 reports are used to identify and track cooperative UAS or Remote-ID-derived UAS
records. Identity does not imply authorization. Core correlates the reported identity against:

- airport and operator authorization lists;
- declared mission/flight windows;
- permitted volumes and altitude bands;
- registration/manufacturer/serial information when present;
- other sensor observations.

The decision result is one of:

```text
cooperative + authorized
cooperative + authorization unknown
cooperative + unauthorized
identity conflict / suspected spoofing
```

Pair ID is retained to associate reports belonging to the same UAS/ground-station context
when supplied by the feed.

## Non-cooperative surveillance: CAT-015 and CAT-016

CAT-015 carries INCS target reports from radar, RF, acoustic, electro-optical, or multisensor
systems. CAT-016 carries the associated INCS configuration/source metadata needed to trace
the contributing transmitter/receiver configuration.

Core must not interpret CAT-016 as an additional target stream. It enriches CAT-015 provenance,
sensor geometry, and health/configuration state.

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
  -> MissionDelegation C-UAS constraints
  -> S1 ORCA3D + final-command validation
```

An interceptor mission is blocked, rerouted, held, or aborted when the delegated safety
constraints cannot be satisfied.

## Health and safety integration

- CAT-063 sensor status contributes to integration health and observation confidence.
- CAT-004 safety-net events are displayed and may trigger Core policy gates, but Furia does
  not fabricate ATC safety-net decisions.
- CAT-253 is not treated as a universal standard. It is enabled only for a named integration
  profile with an agreed UAP and authorization model.

## Security

ASTERIX itself is not treated as an authenticated authority channel. Deployment must provide:

- network segmentation and allow-listed endpoints;
- source identity at the transport/tunnel layer;
- replay protection and sequence monitoring;
- raw-message hashing and immutable audit logs;
- schema/category/edition allow lists;
- bounds checks before allocation or decoding;
- rejection of impossible coordinates, stale timestamps, and conflicting identity data.

Any experimental authentication wrapper or CAT-000 convention must remain outside the
standard category decoder and be explicitly negotiated with the integration partner.

## Bordeaux acceptance sequence

1. CAT-129 reports an authorized inspection UAS.
2. CAT-015 reports a non-cooperative target approaching runway 05/23.
3. CAT-016 metadata links the report to the contributing INCS configuration.
4. Core fuses observations and publishes an internal threat track.
5. CAT-021 reports a crewed aircraft on approach.
6. Core creates a moving protected volume and modifies the interceptor plan.
7. Core delegates a bounded C-UAS contract to S1.
8. S1 executes 3D intercept guidance, ORCA3D, and final-command validation.
9. A degraded communications event causes last-valid-contract continuation.
10. On reconnection, S1 returns execution evidence and assignment generation.
11. The fused non-cooperative track is available for agreed CAT-062 publication.
12. CAT-063 status degradation reduces confidence and is visible in C2.

## Standards baseline

The integration baseline should record the exact editions used at deployment. Initial targets:

- CAT-129 Edition 1.2;
- CAT-015 Edition 1.2;
- CAT-016 Edition 1.0;
- CAT-062 Edition 1.21;
- CAT-021 Edition 2.7;
- CAT-063 current agreed edition/profile.

Operational and performance requirements should be traced to ED-286 / DO-389 and ED-322 /
DO-403 where the documents are available to the programme. Future WG-115 interoperability
requirements should be incorporated through a versioned profile rather than hard-coded assumptions.
