# Qualité et provenance des données géospatiales

## Statut actuel

Les aéroports géospatialement raccordés dans ce dépôt sont LFBD, LFPG, LFPO, LFLL, LFBO, LFRS, LFMN, LFML, LFST, LFQQ, LFMT, LFLS, LFRN, LFRB, LFOB, LFMP, LFRK, LFLC, LFBP, LFBZ, LFLY, LFLB, LFJL, LFSB, LFKJ, LFKC, LFMU, LFMK, LFAT, LFAC, LFMD, LFTH, LFOT, LFBH, LFBI, LFBL, LFSD, LFLP, LFRC, LFRQ, LFRO, LFRH, LFOH, LFAV, LFRD, LFRG, LFOK, LFTW, LFMV, LFCK, LFCR, LFBT, LFBA, LFBX, LFRM, LFOV, LFLD, LFBK, LFOU, LFJR, LFGA, LFGJ, LFPB, LFMH, LFLA, LFCI, LFSL et LFRU. Un inventaire
Les nouveaux packs LFBU, LFBE et LFLW sont également présents et validés par
le contrôle de provenance.
historique séparé (`data/geospatial/france-airports-identity-inventory.json`)
contient 96 identités ICAO issues d’une source publique ancienne ; il ne vaut
pas validation géospatiale. Le registre
[`data/geospatial/france-airports-registry.json`](../data/geospatial/france-airports-registry.json)
reste donc explicitement `partial_inventory` : il ne transforme aucune identité
en pack et n’invente aucune fiche sans données locales vérifiables.

Le contexte LFBD est utilisable pour une démonstration et une étude d’interface,
pas pour une décision opérationnelle : son autorité est `context_only`.

## Constats vérifiés

- DEM principal : source Bordeaux Métropole MNT 2023, échantillon dérivé de
  12 dalles, résolution source annoncée 0,5 m, grille navigateur `192 × 256`.
- La grille affichée est un produit dérivé resamplé ; les rasters sources restent
  nécessaires pour toute étude d’exactitude ou de visibilité sérieuse.
- Bâtiments : 5 850 empreintes/parties issues d’OpenStreetMap dans l’export
  courant.
- 5 773 empreintes n’ont pas de hauteur renseignée. Aucune hauteur n’est
  inventée par le contrôle qualité.
- Le contexte bâtiment ne fournit pas une garantie de complétude, d’actualité,
  de hauteur, de toiture ou d’obstacle aéronautique.
- La référence verticale n’est pas indépendamment certifiée dans ce dépôt.
- Les sources SIA/TOD sont référencées comme sources disponibles, mais ne sont
  pas présentées comme importées ou validées.

## Garde de validation

La commande canonique est :

```bash
make geospatial-provenance-check
```

Elle vérifie notamment :

- schémas et statut `context_only` ;
- ICAO et emprise ordonnée ;
- concordance dimensions/nombre d’échantillons DEM ;
- coordonnées DEM et bâtiments dans l’emprise déclarée ;
- géométries GeoJSON supportées ;
- présence de la licence bâtiment et du catalogue de sources ;
- références locales sans sortie du dépôt ;
- concordance entre le registre, le pack aéroport et le manifeste géospatial ;
- unicité et statut non opérationnel des 96 identités de l’inventaire historique ;
- registre explicitement partiel et sans statut opérationnel implicite.

## Conditions avant usage opérationnel

Chaque nouvel aéroport doit apporter un pack indépendant avec : source et
millésime, emprise, CRS horizontal, référence verticale, résolution, exactitude
ou incertitude, couverture des hauteurs bâtiments, date de contrôle, licence,
empreintes des fichiers et statut de validation par l’exploitant/autorité
compétente. Tant que ces éléments ne sont pas présents, le pack reste un
contexte de simulation et l’interface doit le signaler comme tel.

## Référence géographique actuelle

Le fichier `data/geospatial/france-airports-current-reference.json` rapproche
l’inventaire historique d’un export public OurAirports récent (`airports.csv` et
`runways.csv`). Il contient 96 correspondances sur 96, avec coordonnées et
pistes de référence, ainsi que les empreintes SHA-256 des fichiers importés.

Cette source est une aide de préparation, pas une autorité aéronautique. Les
emprises calculées dans `france-airports-acquisition-queue.json` sont marquées
`derived_for_review_only` et doivent être revues avant toute acquisition
DEM/bâtiments. Un alias explicite est conservé pour le code de facility Tahiti
`NTTT` vers le code aéroport `NTAA` ; il ne constitue pas une autorité
opérationnelle.

La file de préparation n’autorise jamais la création automatique d’un pack à
partir d’une identité seule. Chaque pack doit encore fournir ses sources, sa
licence, sa date de collecte, la qualité des hauteurs et son statut de revue.

## Acquisition reproductible

Les packs peuvent être acquis avec `scripts/acquire_airport_geodata.py` à
partir des coordonnées de référence publiques. Le script interroge l’API IGN
Géoportail RGE ALTI pour le DEM et l’API OSM officielle pour les bâtiments,
conserve les URL, horodatages et empreintes SHA-256, puis refuse de produire un
pack si une couche échoue. Les emprises dérivées d’un point sont marquées
`derived_from_public_reference_point_pending_review` et restent
`context_only`.

Le registre est synchronisé par `scripts/sync_geospatial_registry.py`. Sa
présence dans le registre ne constitue jamais une qualification opérationnelle
ou une validation par la DGAC, le SIA ou l’exploitant.
