# Airport packs

Each airport gets one directory named with its ICAO code and one
`manifest.json`. Copy the LFBD fixture as the starting template, then replace
the five component references with airport-specific files:

```text
<icao>/
├── manifest.json
├── identity.json
├── geodata.json
├── sensors.json
├── sectors.json
└── scenarios.json
```

The component files are intentionally separate so that changing a sensor
catalogue does not silently change airport identity, protected sectors or
scenario timing. Keep all source and display data labelled as context,
training or partner-provided; do not promote synthetic fixtures to operational
authority.

Validate each new pack with:

```bash
python3 scripts/validate_airport_pack.py demo/golden/airport-packs/<ICAO>/manifest.json
```

## Runner resolution

Runners must consume the pack through the generic resolver rather than
constructing paths or branching on an ICAO code. It validates every component,
resolves secondary references, and emits a self-contained JSON document with
repository-relative provenance:

```bash
python3 scripts/resolve_airport_pack.py \
  demo/golden/airport-packs/<ICAO>/manifest.json
```

The resulting `bod-cuas.resolved-airport-pack` document contains `identity`,
`geodata`, `sensors`, `sectors`, and `scenarios` under `components`, plus
`secondary_references` and optional `compatibility` paths. A generic runner can
therefore select an airport pack by manifest path and remain independent of
LFBD, Bordeaux-specific filenames, and demo-only legacy assets.
