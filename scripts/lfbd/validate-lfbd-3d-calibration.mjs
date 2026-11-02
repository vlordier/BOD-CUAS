import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const manifestPath = path.resolve(root, 'data/geospatial/lfbd/manifest.json')
const controlsPath = path.resolve(root, 'data/geospatial/lfbd/lfbd-3d-calibration-control-points.json')
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
const controls = JSON.parse(fs.readFileSync(controlsPath, 'utf8'))
const candidate = manifest.archive_visual_candidate

if (!candidate || candidate.operational_use !== false) {
  throw new Error('LFBD archive candidate must remain explicitly non-operational')
}
if (controls.status !== 'validated' && candidate.status !== 'candidate_unvalidated') {
  throw new Error('Unvalidated calibration cannot be published with a validated asset status')
}
const resolved = controls.points.filter((point) => point.source_local && point.status === 'resolved')
if (resolved.length < controls.acceptance.minimum_resolved_points) {
  console.log(`LFBD 3D calibration pending: ${resolved.length}/${controls.acceptance.minimum_resolved_points} control points resolved`)
  process.exit(0)
}
if (controls.status !== 'validated') {
  throw new Error('Resolved control points require a validated calibration status')
}
console.log(`LFBD 3D calibration ready: ${resolved.length} control points`) 
