# Données

Les fichiers INSEE ne sont pas versionnés (plusieurs centaines de Mo).

## Option 1 : repartir des fichiers bruts INSEE

1. Télécharger les fichiers **Base flux de mobilité résidentielle** 2018 à 2022 :
   https://www.insee.fr/fr/statistiques/7637844
2. Les placer dans `data/raw/` sous la forme `base-flux-mobilite-residentielle-2018.csv`, …, `-2022.csv`.
3. Lancer la préparation :

```bash
python scripts/prepare_insee.py --raw data/raw --out data/flux_migratoire_triee.csv
```

## Option 2 : réutiliser la sortie d'UrbanFlows-FR

Le fichier `outputs/flux_migratoire_triee.csv` produit par le notebook `01_tri_donnees.ipynb`
de [UrbanFlows-FR](https://github.com/amdvii/UrbanFlowsFR) a exactement le bon format :
il suffit de le copier ici en `data/flux_migratoire_triee.csv`.

## Format attendu

CSV séparé par `;` avec les colonnes :

| colonne | description |
|---|---|
| `annee` | millésime INSEE |
| `code_orig` / `nom_orig` | commune de résidence antérieure |
| `code_dest` / `nom_dest` | commune de résidence actuelle |
| `flux` | nombre de personnes (estimation INSEE) |
