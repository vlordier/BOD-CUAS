#!/usr/bin/env node
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const run = promisify(execFile)

const outputDir = resolve(process.env.LFBD_GEOSPATIAL_OUTPUT ?? 'data/geospatial/lfbd')
const south = Number(process.env.LFBD_BBOX_SOUTH ?? 44.8)
const west = Number(process.env.LFBD_BBOX_WEST ?? -0.76)
const north = Number(process.env.LFBD_BBOX_NORTH ?? 44.86)
const east = Number(process.env.LFBD_BBOX_EAST ?? -0.68)
const rows = Number(process.env.LFBD_DEM_ROWS ?? 32)
const cols = Number(process.env.LFBD_DEM_COLS ?? 32)
const overpassUrl = process.env.OVERPASS_URL ?? 'https://overpass-api.de/api/interpreter'
const retrievedAt = new Date().toISOString()

if (![south, west, north, east, rows, cols].every(Number.isFinite) || south >= north || west >= east) {
  throw new Error('Invalid LFBD bbox or DEM grid dimensions')
}

const requestJson = async (url, init = {}) => {
  const args = ['--http1.1', '--fail', '--silent', '--show-error', '--retry', '4', '--retry-delay', '2', '-H', 'accept: application/json', '-H', 'user-agent: furia-cuas-geodata-import/1.0']
  if (init.method) args.push('-X', init.method)
  for (const [key, value] of Object.entries(init.headers ?? {})) args.push('-H', `${key}: ${value}`)
  if (init.body) args.push('--data', init.body)
  args.push(String(url))
  const { stdout } = await run('curl', args, { maxBuffer: 64 * 1024 * 1024 })
  return JSON.parse(stdout)
}

const coordinates = []
for (let row = 0; row < rows; row += 1) {
  for (let col = 0; col < cols; col += 1) {
    coordinates.push({
      lat: south + ((north - south) * row) / Math.max(1, rows - 1),
      lon: west + ((east - west) * col) / Math.max(1, cols - 1),
    })
  }
}

const delimiter = '|'
const elevationUrl = new URL('https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json')
const elevation = await requestJson(elevationUrl, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    lon: coordinates.map(({ lon }) => lon).join(delimiter),
    lat: coordinates.map(({ lat }) => lat).join(delimiter),
    resource: 'ign_rge_alti_wld',
    delimiter,
    indent: 'false',
    measures: 'false',
    zonly: 'false',
  }),
})
const elevations = (elevation.elevations ?? []).filter((sample) => Number.isFinite(sample.z) && sample.z > -90000)
if (elevations.length !== coordinates.length) {
  throw new Error(`IGN returned ${elevations.length}/${coordinates.length} valid elevation samples`)
}

// Include building parts and roof metadata: these are the highest-resolution
// public exterior descriptors available without an airport BIM/scan. They are
// still contextual OSM data, never an obstacle certification.
const overpassQuery = `[out:json][timeout:180];way["building"](${south},${west},${north},${east});out tags geom;`
const overpass = await requestJson(overpassUrl, {
  method: 'POST',
  headers: { 'content-type': 'application/x-www-form-urlencoded' },
  body: `data=${encodeURIComponent(overpassQuery)}`,
})
const features = (overpass.elements ?? []).flatMap((element) => {
  const geometry = element.geometry ?? []
  if (geometry.length < 3) return []
  const ring = geometry.map(({ lon, lat }) => [lon, lat])
  const first = ring[0]
  const last = ring[ring.length - 1]
  if (first[0] !== last[0] || first[1] !== last[1]) ring.push(first)
  const tags = element.tags ?? {}
  const heightM = Number.parseFloat(String(tags.height ?? '').replace(',', '.'))
  const levels = Number.parseFloat(String(tags['building:levels'] ?? '').replace(',', '.'))
  const minHeightM = Number.parseFloat(String(tags.min_height ?? '').replace(',', '.'))
  const roofHeightM = Number.parseFloat(String(tags['roof:height'] ?? '').replace(',', '.'))
  return [{
    type: 'Feature',
    id: `osm-way-${element.id}`,
    properties: {
      osm_id: element.id,
      building: tags.building ?? 'yes',
      building_part: tags.building === 'part',
      name: tags.name ?? null,
      height_m: Number.isFinite(heightM) ? heightM : Number.isFinite(levels) ? levels * 3 : null,
      height_source: Number.isFinite(heightM) ? 'OSM height' : Number.isFinite(levels) ? 'OSM building:levels' : null,
      min_height_m: Number.isFinite(minHeightM) ? minHeightM : null,
      roof_height_m: Number.isFinite(roofHeightM) ? roofHeightM : null,
      roof_shape: tags['roof:shape'] ?? null,
      roof_material: tags['roof:material'] ?? null,
      levels: Number.isFinite(levels) ? levels : null,
    },
    geometry: { type: 'Polygon', coordinates: [ring] },
  }]
})

await mkdir(outputDir, { recursive: true })
await writeFile(resolve(outputDir, 'terrain-grid.json'), `${JSON.stringify({
  schema: 'furia.cuas.terrain-grid',
  version: '1.1.0',
  source: 'IGN Géoplateforme · RGE ALTI',
  source_url: elevationUrl.toString(),
  resource: 'ign_rge_alti_wld',
  license: 'Licence ouverte / Etalab',
  bbox: { south, west, north, east },
  rows,
  cols,
  resolution_approx_m: ((north - south) * 111003) / Math.max(1, rows - 1),
  elevations,
  quality: { requested_points: coordinates.length, returned_points: elevation.elevations?.length ?? 0, valid_points: elevations.length },
  retrieved_at: retrievedAt,
  limitations: ['MNT de contexte, échantillonné à 32 × 32 points', 'Ne remplace pas une base obstacle ou une validation aéronautique'],
}, null, 2)}\n`)
await writeFile(resolve(outputDir, 'buildings.geojson'), `${JSON.stringify({
  type: 'FeatureCollection',
  features,
  metadata: {
    source: 'OpenStreetMap contributors',
    source_url: overpassUrl,
    license: 'ODbL 1.0',
    overpass_query: overpassQuery,
    retrieved_at: retrievedAt,
    limitations: ['Hauteurs absentes pour une partie des bâtiments', 'Parties de bâtiment et toitures publiques partielles', 'Empreintes de contexte uniquement, non certifiées obstacle'],
  },
}, null, 2)}\n`)
await writeFile(resolve(outputDir, 'manifest.json'), `${JSON.stringify({
  schema: 'furia.cuas.airport-geospatial-context',
  version: '1.1.0',
  airport_icao: 'LFBD',
  authority: 'context_only',
  bbox: { south, west, north, east },
  layers: { terrain: 'terrain-grid.json', buildings: 'buildings.geojson' },
  sources: ['IGN Géoplateforme · RGE ALTI', 'OpenStreetMap contributors'],
  license: ['Licence ouverte / Etalab', 'ODbL 1.0'],
  retrieved_at: retrievedAt,
  limitations: ['Contexte de simulation et de visualisation uniquement', 'Ne remplace pas TOD, AIP, NOTAM, obstacle database ou validation aéroportuaire'],
}, null, 2)}\n`)
await writeFile(resolve(outputDir, 'source-catalog.json'), `${JSON.stringify({
  schema: 'furia.cuas.geospatial-source-catalog',
  version: '1.1.0',
  airport_icao: 'LFBD',
  sources: [
    { id: 'ign-rge-alti', kind: 'terrain_dem', provider: 'IGN Géoplateforme', url: 'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json', license: 'Licence ouverte / Etalab', status: 'imported_live', resolution_or_lod: `${rows} × ${cols} samples`, limitations: ['Échantillonnage de contexte'] },
    { id: 'osm-buildings', kind: 'building_footprints_and_parts', provider: 'OpenStreetMap contributors', url: overpassUrl, license: 'ODbL 1.0', status: 'imported_live', resolution_or_lod: `${features.length} empreintes/parties`, limitations: ['Hauteurs et parties de toiture incomplètes', 'Validation nécessaire'] },
    { id: 'bordeaux-mnt-2023', kind: 'terrain_dem', provider: 'Bordeaux Métropole', url: 'https://www.data.gouv.fr/datasets/modele-numerique-de-terrain-2023', license: 'Licence Ouverte', status: 'available_external_not_imported', resolution_or_lod: 'Raster GeoTIFF · pixel 0,5 m', limitations: ['Téléchargement multi-dalles externe', 'À intégrer dans un pipeline lourd hors démo'] },
    { id: 'sia-tod-lfbd', kind: 'aeronautical_terrain_and_obstacles', provider: 'Service de l’information aéronautique', url: 'https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/donnees-tod/donnees-de-terrain-et-d-obstacles-de-bordeaux-lfbd.html', license: 'Conditions SIA', status: 'available_reference_not_imported', resolution_or_lod: 'ASC MNT + SHP obstacles', limitations: ['Édition publique consultée 2019', 'Ne fournit pas la maquette intérieure du terminal'] },
    { id: 'bordeaux-bati3d-2012', kind: 'textured_3d_buildings_and_terrain', provider: 'Bordeaux Métropole DataHub', url: 'https://datahub.bordeaux-metropole.fr/explore/dataset/bati3d/', license: 'Open data terms as published by Bordeaux Métropole', status: 'historical_reference', resolution_or_lod: 'LOD2 · millésime 2012', limitations: ['Donnée historique'] },
  ],
  provenance_policy: 'Chaque couche conserve sa source, licence, date, résolution et statut d’autorité.',
}, null, 2)}\n`)
console.log(`Imported real LFBD geodata: ${elevations.length} IGN elevations, ${features.length} OSM buildings -> ${outputDir}`)
