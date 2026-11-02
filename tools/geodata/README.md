# Import géospatial context

Pour LFBD, le raccourci historique reste disponible. Pour tout autre aéroport,
utiliser l’importeur générique et fournir explicitement une emprise validée par
l’utilisateur :

```bash
python3 tools/geodata/import_airport_open_data.py \
  --icao LFXX --bbox 44.80 -0.76 44.86 -0.68 \
  --output data/geospatial/lfxx --rows 32 --cols 32
```

L’importeur ne crée pas d’emprise à partir du seul code ICAO. Une identité
d’aéroport n’est pas une géométrie. Chaque sortie reste `context_only` et doit
passer `make geospatial-provenance-check` ou `scripts/validate_geospatial_provenance.py`
avant d’être consommée par la simulation.

```bash
python3 tools/geodata/import_lfbd_open_data.py --rows 32 --cols 32
```

L’importeur récupère :

- les altitudes via l’API ouverte IGN Géoplateforme / RGE ALTI ;
- les emprises bâties via OpenStreetMap/Overpass, avec hauteur issue des tags disponibles.
- un instantané météo public optionnel via `python3 tools/geodata/fetch_lfbd_weather.py`.

Il écrit `data/geospatial/lfbd/terrain-grid.json`, `buildings.geojson` et `manifest.json`, en conservant source,
licence, date, qualité et limitations. Le contrôle canonique est `make geospatial-provenance-check`. Le manifest est `context_only` : il ne constitue ni une base d’obstacles,
ni une donnée TOD, ni une source ATC.
