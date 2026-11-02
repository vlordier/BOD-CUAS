# Live-context bridge

This is the safe route from a compelling training demo to a real-context
demonstrator. It has **no command or authority path**.

It supports three additive feed classes:

| Source | Input | NATS output | Trust boundary |
|---|---|---|---|
| Local ADS-B receiver | JSON Lines export | `surveillance.observation` CAT021 / `crewed_aircraft` | Local observation, not ATC truth |
| Local Remote ID receiver | JSON Lines export | `surveillance.observation` CAT129 / `cooperative_uas` | Identity broadcast, never authorisation |
| Approved METAR API | JSON HTTP | `environment.weather.observation` | Display context, not aircraft performance authority |

## Hybrid public-context snapshot

`real_context_adapter.py` adds a bounded, repeatable public-context layer for
the presentation. It fetches an LFBD-area OpenSky state-vector box and the
LFBD METAR, writes hashed snapshots to a local cache, and emits a single
`furia.cuas.mixed-context-snapshot` artifact. Use the cache during a demo so
the incident remains deterministic:

```bash
python3 demo/live-context/real_context_adapter.py \
  --output data/lfbd-mixed-context.json
python3 demo/live-context/real_context_adapter.py \
  --output data/lfbd-mixed-context.json --no-network

# Publish the same cached artifact to the demo's context-only NATS subjects.
python3 demo/live-context/real_context_adapter.py \
  --output data/lfbd-mixed-context.json --no-network \
  --nats-url nats://127.0.0.1:4222
```

OpenSky aircraft and public weather are contextual observations only. They
must never be presented as ATC truth, flight clearance, or a source of C-UAS
authority. The hostile UAS, sensor disagreement, airport-operation state,
authority contract and S1 evidence remain training-simulated.

`hybrid-demo-scenario.json` is the presenter script: it joins real/cached
airport context to the synthetic detect → assess → conflict → safe-hold story
and defines four what-if branches for counterfactual playback.

`source-catalog.json` is the source-of-truth inventory for the full demo. It
classifies every C2 claim as `real_adapter`, `training_simulator`, or
`requires_partner`; the accompanying test rejects any ambiguous source state.

Run the checked-in receiver samples against a running NATS server:

```bash
python3 demo/live-context/context_bridge.py --config demo/live-context/context-sources.example.json
```

Validate the supplied local fixtures without NATS with `--dry-run`.

To add a contracted weather endpoint, copy this source into a local config
(never commit its URL or credential):

```json
{"id":"lfbd-metar","kind":"metar_http_json","provider":"approved Météo-France provider","airport_icao":"LFBD","url":"https://approved-provider.example/metar/LFBD","bearer_token_env":"METEO_FRANCE_TOKEN"}
```

## Real deployment

1. The supplied configuration fetches the latest public LFBD METAR from the
   NOAA Aviation Weather API. It is external context only; source and receipt
   time remain visible in the event.
2. Replace the JSONL export paths with the controlled receiver export process.
3. Give every deployed receiver a stable SAC/SIC and protect its source host.
4. Configure an approved Météo-France provider URL and provide its credential
   only through `METEO_FRANCE_TOKEN`; credentials are never committed.
5. Keep the golden replay/S1 sequence labelled `training_replay`. A live
   receiver must never enable mission authority, aircraft clearance or effects.

The bridge deliberately does **not** invent an airport AODB, DSNA radar,
U-space network-ID, ATC clearance, or RF/EO/IR feed. Those interfaces require
the respective operator agreement and a source-specific adapter.

## AIRAC / terrain / obstacle import boundary

`static_context_import.py` accepts a reviewed GeoJSON conversion of downloaded
SIA AIXM or LFBD TOD material and emits a versioned, checksummed C2 context
artifact. The committed manifest points at the training geometry until a
reviewed source download replaces it; it is never silently promoted to an
airport-operational source.

## Bordeaux 3D visual context

`acquire_lfbd_bati3d.sh` downloads a bounded, verified package from Bordeaux
Métropole's open Bati3D catalogue.  It is a textured **2012** model, so the
only permitted C2/scene label is `Bordeaux Metropole Bati3D (2012) · CONTEXT
ONLY`. It is not an obstacle database, airport-layout source, or video feed.

```bash
make verify-bati3d       # integrity and provenance check
make bati3d-index        # inspect 1,260 available 200 m tiles without extraction
make bati3d-core         # bounded LFBD core extraction (35 tiles / 1.4 x 1 km)
make bati3d-web          # convert the extracted core to browser-loadable GLB tiles
```

`scripts/build_lfbd_bati3d_web.py` converts the reviewed subset with Assimp
into browser-loadable GLB tiles and writes
`data/lfbd/bati3d/web/manifest.json`. The C2 viewer loads those tiles through
Three.js in the same local LFBD ENU frame. The web asset remains context-only:
it is never current airport truth, obstacle data, or sensor authority.

`RealGazebo/tools/bordeaux/prepare_lfbd_bati3d_fbx.py` converts that reviewed
subset with Assimp into a manifest that maps each tile from EPSG:3945 to the
LFBD world origin. The corresponding Unreal importer tags every actor
`HistoricalBati3D2012`, `FuriaContextOnly`, and `NoOperationalAuthority`.

## Offline rehearsal simulators

Use this only when presenting without an external provider:

```bash
python3 demo/live-context/context_simulator.py --nats-url nats://127.0.0.1:4222
```

It emits weather, airport-operations and U-space **context-only** subjects,
each marked `training_simulation`. The C2 therefore exposes them as an
integrated context feed with their limitations rather than as airport authority.

### 3D visual-world descriptor

When the RealGazebo/Bati3D training world is running, publish its display-only
descriptor alongside the normal rehearsal context:

```bash
python3 demo/live-context/visual_world_simulator.py --nats-url nats://127.0.0.1:4222
```

It emits `cuas.visual-world.context`. C2 shows its coverage, renderer and
provenance in the tactical-map context card. This is deliberately **not** a
position, obstacle, runway-state, navigation, authority or video contract.
The supplied world is labelled `Bordeaux Métropole Bati3D (2012) · CONTEXT
ONLY`; all airport operational geometry remains a separate reviewed import.

`eo_ir_simulator.py` supplies a continuous, moving, KLV-shaped metadata stream
for PTZ-2. It intentionally contains no imagery; the C2 labels it `SIMULATED
KLV` rather than presenting a synthetic viewport as live video.
