# Générateur générique d’Airport Pack

`scripts/build_airport_pack.py` transforme une configuration source minimale
en un pack autonome consommable par le runtime et l’UI. Le moteur ne contient
aucun ICAO, aucune coordonnée ni hypothèse propre à un aéroport.

```bash
python3 scripts/build_airport_pack.py config/airport-pack-builder.example.json \
  --output /tmp/airport-pack
python3 scripts/validate_airport_pack.py /tmp/airport-pack/manifest.json
```

La sortie contient le manifest, l’identité, le profil opérateur, le catalogue
capteurs/intercepteurs, la géodata et sa provenance, les capteurs, secteurs,
volumes, scénarios et `validation-report.json`.
Le builder exécute automatiquement le validateur du dépôt et ne marque le
rapport `validated` que lorsque le pack généré est cohérent.

Les champs obligatoires sont `icao`, `iata`, `name`, `country`,
`reference_point` et `bounds`. Les autres composants sont configurables. En
leur absence, le builder crée des éléments synthétiques explicitement marqués
`training_only`, afin que le pack soit testable sans prétendre représenter une
capacité réelle.

Le builder ne télécharge aucune donnée et ne certifie ni la géométrie, ni les
obstacles, ni les performances des capteurs/intercepteurs. Tous les packs
produits sont `training_only`; une qualification humaine et réglementaire reste
nécessaire avant tout usage opérationnel.
