"""Prépare les fichiers bruts INSEE pour DataChat-FR.

Reprend l'ETL d'UrbanFlows-FR (notebook 01_tri_donnees) :
- lecture des fichiers base-flux-mobilite-residentielle-{annee}.csv
- détection automatique de la colonne NBFLUX_* (son nom change selon le millésime)
- suppression des flux venant de l'étranger (codes 99xxx), des flux intra-communaux et des flux nuls
- fusion des millésimes dans data/flux_migratoire_triee.csv

Usage :
    python scripts/prepare_insee.py --raw data/raw --out data/flux_migratoire_triee.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

RENOMMAGE = {"CODGEO": "code_dest", "LIBGEO": "nom_dest", "DCRAN": "code_orig", "L_DCRAN": "nom_orig"}


def lire_millesime(chemin: Path) -> pd.DataFrame:
    annee = int(re.search(r"(20\d{2})", chemin.stem).group(1))
    try:
        df = pd.read_csv(chemin, sep=";", dtype={"CODGEO": str, "DCRAN": str})
    except UnicodeDecodeError:  # certains millésimes sont encodés en Latin-1
        df = pd.read_csv(chemin, sep=";", dtype={"CODGEO": str, "DCRAN": str}, encoding="latin-1")
    col_flux = next(c for c in df.columns if c.startswith("NBFLUX"))
    df = df.rename(columns={**RENOMMAGE, col_flux: "flux"})
    df["annee"] = annee
    df = df[~df["code_orig"].str.startswith("99", na=False)]
    df = df[df["code_dest"] != df["code_orig"]]
    df = df.dropna(subset=["flux"])
    df = df[df["flux"] > 0]
    print(f"  {chemin.name} : {len(df):,} flux".replace(",", " "))
    return df[["annee", "code_orig", "nom_orig", "code_dest", "nom_dest", "flux"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", default="data/raw", help="Dossier des CSV INSEE bruts")
    parser.add_argument("--out", default="data/flux_migratoire_triee.csv")
    args = parser.parse_args()

    fichiers = sorted(Path(args.raw).glob("base-flux-mobilite-residentielle-*.csv"))
    if not fichiers:
        raise SystemExit(f"Aucun fichier base-flux-mobilite-residentielle-*.csv dans {args.raw}")

    print("Lecture des millésimes INSEE :")
    flux = pd.concat([lire_millesime(f) for f in fichiers], ignore_index=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    flux.to_csv(args.out, sep=";", index=False)
    print(f"✅ {len(flux):,} flux enregistrés dans {args.out}".replace(",", " "))


if __name__ == "__main__":
    main()
