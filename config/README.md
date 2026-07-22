# Bordeaux C-UAS demo configuration

The C-UAS director loads cooperative-UAS authorization policy from:

```text
$UXV_CONFIG_DIR/cuas-authorizations.yaml
```

For the Bordeaux demo, `demo/golden/run.sh` points `UXV_CONFIG_DIR` at this `config/` directory.

The policy deliberately exercises three operator-visible states:

- `uas:FR:DJI:M30:0102030405060708090a0b0c` is authorized inside the Bordeaux-area 3D volume through the configured validity window.
- `uas:FR:EXP:OLD:eeeeeeeeeeeeeeeeeeeeeeee` is a known identity with an expired authorization and therefore resolves to `cooperative + unauthorized`.
- Any CAT129 identity absent from the file remains `cooperative + authorization unknown`; it is not implicitly authorized and is not automatically classified hostile.

Authorization is evaluated by Furia Core after CAT129 decoding. The CAT129 decoder itself only establishes cooperative identity/state and preserves ASTERIX provenance.

The YAML is schema-versioned (`version: 1`), bounded by Core, and unknown fields or invalid rules cause the policy load to fail closed to an empty authorization registry.
