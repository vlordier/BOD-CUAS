# Propriété des données LFBD

Le registre canonique de propriété est [`../contracts/lfbd-demo-ownership.json`](../contracts/lfbd-demo-ownership.json).
Il inventorie explicitement les profils, scénarios, stories, fixtures, catalogues fournisseurs, outils d'import et
assets géospatiaux. Toute nouvelle donnée LFBD doit être ajoutée à ce registre avant d'être consommée par une démo.

Validation locale :

```bash
make ownership-check
```

Les stories LFBD sont actuellement volontairement absentes de ce dépôt (`stories: []`). Les stories de composants
génériques appartiennent à `furia-ui`; une story LFBD devra être créée sous `demo/stories/lfbd/` et enregistrée dans
le manifeste. Cela évite de confondre une story de démonstration aéroportuaire avec une primitive UI.

Les données et outils sous `data/geospatial/lfbd/`, `scripts/lfbd/` et
`tools/geodata/` sont propres à l'aéroport de Bordeaux-Mérignac (LFBD). Ils
appartiennent à `BOD-CUAS`, qui porte les packs aéroport, les imports, les
assets et leur provenance.

`furia-core` ne contient que les contrats et calculs génériques nécessaires à
la consommation d'un pack. `furia-cuas` exécute la logique de domaine et
publie la projection validée. `furia-ui` reçoit un artefact explicitement
configuré via les alias d'aéroport ; il ne doit pas importer une donnée LFBD
depuis le dépôt du moteur.

La présence d'une donnée dans ce dépôt ne constitue ni une validation
opérationnelle, ni une donnée ATC, ni une autorisation d'emploi. Les profils,
scénarios et fixtures sont des artefacts de démonstration; leur provenance et
leur statut doivent rester visibles pour tout consommateur.
