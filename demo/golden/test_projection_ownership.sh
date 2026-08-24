#!/usr/bin/env bash
set -euo pipefail

# Network-free regression gate for the canonical synthetic demo topology.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAUNCHER="$ROOT_DIR/BOD-CUAS/demo/golden/run.sh"
DOMAIN="$ROOT_DIR/furia-cuas/crates/furia-cuas-domain/src/lib.rs"
UI_CONTRACT="$ROOT_DIR/furia-ui/packages/cuas-contracts/src/operationalProjection.ts"

bash -n "$LAUNCHER"
grep -Fq 'DEMO_CUAS_PROJECTION_MODE' "$LAUNCHER"
grep -Fq 'CUAS_CANONICAL_PROJECTION_PRODUCER="$CUAS_PROJECTION_MODE"' "$LAUNCHER"
grep -Fq 'furia-cuas-publisher' "$LAUNCHER"
grep -Fq 'canonical.producer = Some' "$ROOT_DIR/furia-cuas/crates/furia-cuas-simulator/src/publisher.rs"
grep -Fq 'pub producer: Option<String>' "$DOMAIN"
grep -Fq 'producer: z.string().trim().min(1).optional()' "$UI_CONTRACT"

echo "C-UAS canonical projection ownership tests: passed"
