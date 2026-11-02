# Airport-pack manifest

An airport pack is the BOD-CUAS boundary for airport-specific demonstration
data. It is deliberately a manifest of independent, versioned components:

| Component | Contains | Does not contain |
| --- | --- | --- |
| `identity` | ICAO/IATA identity, reference point, display bounds and CRS | live authority or current operational truth |
| `geodata` | terrain/building/visual-context references and provenance | generic 3D primitives or navigation authority |
| `sensors` | airport sensor placements, modalities and source references | sensor-fusion algorithms |
| `sectors` | named airport sectors and links to policy-volume fixtures | generic coverage equations or commands |
| `scenarios` | replay/resilience scenario entrypoints and fixtures | live execution authority |

The contract is described by [`airport-pack.schema.json`](./airport-pack.schema.json).
The LFBD example is [`demo/golden/airport-packs/lfbd/manifest.json`](../demo/golden/airport-packs/lfbd/manifest.json).
It is synthetic/training-only and keeps compatibility references to the existing
LFBD golden fixtures while the pack becomes the stable discovery boundary.

Validate a pack with:

```bash
python3 scripts/validate_airport_pack.py demo/golden/airport-packs/lfbd/manifest.json
```

Every reference is resolved relative to the file that declares it and is
forbidden from escaping the BOD-CUAS repository. A future airport adds another directory under
`demo/golden/airport-packs/<icao>/` without changing the validator or any
shared Core/UI code.

The pack is context only. It must never be used to imply current AIP data,
certified obstacle data, ATC authority, sensor certification, or authority to
execute an effect.
