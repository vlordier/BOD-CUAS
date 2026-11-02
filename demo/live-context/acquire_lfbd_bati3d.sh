#!/usr/bin/env bash
# Download the bounded Bordeaux Metropole Bati3D package used for LFBD context.
# The raw archive is intentionally ignored by Git; its provenance lives beside it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST_DIR="${LFBD_BATI3D_DIR:-$ROOT/data/lfbd/bati3d}"
ARCHIVE="$DEST_DIR/bati3d-lfbd-2012-3ds.zip"
WPS_URL="https://data.bordeaux-metropole.fr/wps"
PUBLIC_KEY="258BILMNYZ"
TILES=(
  HK HL HM HN IH II IJ IK IL IM IN JH JI JJ JK JL JM JN KH KI KJ KK KL KM KN
  LH LI LJ LK LL LM LN MH MI MJ MK ML MM MN
)

if [[ "${1:-}" == "--verify" ]]; then
  test -f "$ARCHIVE"
  unzip -t "$ARCHIVE" >/dev/null
  shasum -a 256 "$ARCHIVE"
  exit 0
fi

mkdir -p "$DEST_DIR"
data_inputs="couche=BATI3D;format=3DS"
for tile in "${TILES[@]}"; do data_inputs+=";dalle=$tile"; done

download_url="$({
  LC_ALL=C curl -fsSLG "$WPS_URL" \
    --data-urlencode "key=$PUBLIC_KEY" \
    --data-urlencode 'service=wps' \
    --data-urlencode 'version=1.0.0' \
    --data-urlencode 'request=execute' \
    --data-urlencode 'identifier=gd_download' \
    --data-urlencode "datainputs=$data_inputs" \
  | iconv -f ISO-8859-1 -t UTF-8 2>/dev/null \
  | sed -n 's/.*<wps:Reference[^>]*href="\([^"]*\)".*/\1/p'
} | head -n 1)"

test -n "$download_url" || { echo "Bati3D downloader did not return an archive URL" >&2; exit 1; }
printf 'Downloading %d LFBD Bati3D tiles to %s\n' "${#TILES[@]}" "$ARCHIVE"
curl -fL --retry 3 --continue-at - "$download_url" -o "$ARCHIVE"
unzip -t "$ARCHIVE" >/dev/null
shasum -a 256 "$ARCHIVE"
