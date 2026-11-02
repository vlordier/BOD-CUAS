#!/usr/bin/env python3
"""Convert the reviewed LFBD Bati3D 3DS core into a browser-ready GLB.

The resulting asset is visual context only. It is deliberately not used as
airport, obstacle, navigation, or sensor-authority data.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import subprocess
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, default=Path('data/lfbd/bati3d/extracted-core'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/lfbd/bati3d/web'))
    parser.add_argument('--assimp', default='assimp')
    parser.add_argument('--archive', type=Path, default=Path('data/lfbd/bati3d/bati3d-lfbd-2012-3ds.zip'))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    texture_names = set()
    # The reviewed source is a zip of outer-tile zips. Extract only the JPEG
    # references for the bounded core; GLB keeps these as same-directory URIs.
    if args.archive.is_file():
        tile_ids = {p.stem.removeprefix('tile_') for p in args.source_dir.glob('x*/tile_x*.3ds')}
        with zipfile.ZipFile(args.archive) as outer:
            for outer_name in outer.namelist():
                if not outer_name.lower().endswith('.zip'):
                    continue
                with zipfile.ZipFile(BytesIO(outer.read(outer_name))) as nested:
                    for member in nested.namelist():
                        parts = member.split('/')
                        tile_part = next((part for part in parts if part.startswith('tile_x') and part.endswith('.3ds') is False), '')
                        tile_id = tile_part.removeprefix('tile_') if tile_part else ''
                        if tile_id not in tile_ids or not member.lower().endswith('.jpg'):
                            continue
                        target = args.output_dir / Path(member).name
                        target.write_bytes(nested.read(member))
                        texture_names.add(target.name)
    # Assimp is used instead of Blender's native 3DS importer: the latter is
    # not stable in headless macOS builds, while Assimp is deterministic here.
    for source in sorted(args.source_dir.glob('x*/tile_x*.3ds')):
        tile_id = source.stem.removeprefix('tile_')
        output = args.output_dir / f'{tile_id}.glb'
        subprocess.run([args.assimp, 'export', str(source), str(output), '-fglb2'], check=True, stdout=subprocess.DEVNULL)
        parts = tile_id.split('y')
        x_index, y_index = int(parts[0][1:]), int(parts[1])
        tiles.append({
            'id': tile_id,
            'asset': output.name,
            'source_3ds': str(source.relative_to(args.source_dir)),
            'east_m': 1401400 + (x_index - 49) * 200 + 100 - 1406316.775,
            'north_m': 4184000 + (y_index - 102) * 200 + 100 - 4187689.405,
        })
    manifest = {
        'schema': 'furia.lfbd.bati3d-web-manifest', 'version': '1.0.0',
        'asset': 'multi-tile', 'tile_count': len(tiles),
        'coordinate_frame': 'local LFBD ENU; x=east, y=up, z=north',
        'materials': 'Bati3D JPEG texture references resolved beside GLB',
        'texture_count': len(texture_names),
        'origin': {'lat': 44.828611, 'lon': -0.715278, 'epsg3945': [1406316.775, 4187689.405]},
        'source': 'Bordeaux Métropole Bati3D (2012)', 'authority': 'context_only',
        'prohibited_claims': ['current airport layout', 'obstacle authority', 'live EO/IR imagery'],
        'tiles': tiles,
    }
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if manifest.get('authority') != 'context_only' or not tiles:
        raise SystemExit('invalid Bati3D web build: missing asset or authority boundary')
    print(f"built Bati3D web pack ({manifest['tile_count']} tiles)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
