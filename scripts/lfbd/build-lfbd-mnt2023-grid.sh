#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RAW_DIR="${1:-$ROOT_DIR/data/geospatial/lfbd/raw/mnt2023}"
OUTPUT="${2:-$ROOT_DIR/data/geospatial/lfbd/terrain-grid-mnt2023.json}"
WORK_DIR="${TMPDIR:-/tmp}/furia-lfbd-mnt2023-grid"
ROWS="${LFBD_TERRAIN_ROWS:-192}"
COLS="${LFBD_TERRAIN_COLS:-256}"

mkdir -p "$WORK_DIR" "$(dirname "$OUTPUT")"

gdalbuildvrt -overwrite "$WORK_DIR/mnt2023.vrt" "$RAW_DIR"/*.tif >/dev/null
gdalwarp -overwrite -q -t_srs EPSG:4326 -te -0.7458954 44.8214 -0.6745517 44.8485 \
  -ts "$COLS" "$ROWS" -r bilinear -dstnodata -9999 \
  "$WORK_DIR/mnt2023.vrt" "$WORK_DIR/mnt2023-wgs84.tif"
gdal_fillnodata.py -q -md 1000 "$WORK_DIR/mnt2023-wgs84.tif" "$WORK_DIR/mnt2023-filled.tif"
gdal_translate -q -of XYZ "$WORK_DIR/mnt2023-filled.tif" "$WORK_DIR/mnt2023.xyz"

OUTPUT="$OUTPUT" XYZ_PATH="$WORK_DIR/mnt2023.xyz" ROWS="$ROWS" COLS="$COLS" node <<'NODE'
const fs = require('node:fs')
const output = process.env.OUTPUT
const xyzPath = process.env.XYZ_PATH
const rows = Number(process.env.ROWS)
const cols = Number(process.env.COLS)
const values = fs.readFileSync(xyzPath, 'utf8')
  .trim().split(/\n/).map((line) => line.trim().split(/\s+/).map(Number))
  .filter(([, , z]) => Number.isFinite(z) && z > -9990)

if (values.length !== rows * cols) throw new Error(`unexpected sample count: ${values.length}`)

const elevations = values.map(([lon, lat, z]) => ({
  lon: Number(lon.toFixed(8)),
  lat: Number(lat.toFixed(8)),
  z: Number(z.toFixed(3)),
  acc: '0.5 m source · bilinear import',
}))

const document = {
  schema: 'furia.cuas.terrain-grid',
  version: '2.0.0',
  source: 'Bordeaux Métropole · MNT 2023',
  source_url: 'https://www.data.gouv.fr/datasets/modele-numerique-de-terrain-2023',
  download_url: 'https://data.bordeaux-metropole.fr/opendata/graphic_downloader/?format=57&layer=183',
  license: 'Licence Ouverte / Etalab',
  airport_icao: 'LFBD',
  bbox: { south: 44.8214, west: -0.7458954, north: 44.8485, east: -0.6745517 },
  source_resolution_m: 0.5,
  resolution_approx_m: 18.5,
  rows,
  cols,
  resampling: 'bilinear',
  vertical_reference: 'RGF93 / CC45 source; vertical datum as supplied by Bordeaux Métropole',
  operational_status: 'context_only',
  elevations,
  limitations: [
    'Grille navigateur resamplée depuis les GeoTIFF MNT2023; les rasters bruts restent la référence de calcul.',
    'Ne remplace pas une base obstacles, le TOD, l’AIP, les NOTAM ou une validation aéroportuaire.',
  ],
}
fs.writeFileSync(output, JSON.stringify(document))
NODE

echo "Generated $OUTPUT ($ROWS x $COLS samples)"
