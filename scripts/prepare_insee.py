import argparse
import re
from pathlib import Path

import pandas as pd

# Prépare les fichiers bruts INSEE pour DataChat-FR.
# C'est le même ETL que dans UrbanFlows-FR (notebook 01_tri_donnees) :
#   - lecture des base-flux-mobilite-residentielle-{annee}.csv
#   - suppression des flux venant de l'étranger, des flux dans la même ville et des flux vides
#   - fusion de toutes les années dans data/flux_migratoire_triee.csv
#
# Utilisation :
#   python scripts/prepare_insee.py --raw data/raw --out data/flux_migratoire_triee.csv


def lire_annee(chemin):
    annee = int(re.search(r'(20\d{2})', chemin.stem).group(1))

    #certaines années sont encodées en latin-1
    try:
        df = pd.read_csv(chemin, sep=';', dtype={'CODGEO': str, 'DCRAN': str})
    except UnicodeDecodeError:
        df = pd.read_csv(chemin, sep=';', dtype={'CODGEO': str, 'DCRAN': str}, encoding='latin-1')

    #le nom de la colonne des flux change selon l'année (NBFLUX_C18_POP01P, etc)
    nom_col_flux = ''
    for col in df.columns:
        if 'NBFLUX' in col:
            nom_col_flux = col

    #On renomme pour + de clarté
    df = df.rename(columns={
        'CODGEO': 'code_dest',
        'LIBGEO': 'nom_dest',
        'DCRAN': 'code_orig',
        'L_DCRAN': 'nom_orig',
        nom_col_flux: 'flux'
    })
    df['annee'] = annee
    df = df[~df['code_orig'].str.startswith('99', na=False)] #les flux venant de l'étranger (99) sont supprimés
    df = df[df['code_dest'] != df['code_orig']] #les personnes qui déménagent dans la même ville sont supprimées
    df = df.dropna(subset=['flux']) #on enlève les cases vides ou = à zéro
    df = df[df['flux'] > 0]

    nb = f"{len(df):,}".replace(',', ' ')
    print(f"  {chemin.name} : {nb} flux")
    return df[['annee', 'code_orig', 'nom_orig', 'code_dest', 'nom_dest', 'flux']]


def main():
    parser = argparse.ArgumentParser(description="Prépare les fichiers bruts INSEE pour DataChat-FR")
    parser.add_argument('--raw', default='data/raw', help="Dossier des CSV INSEE bruts")
    parser.add_argument('--out', default='data/flux_migratoire_triee.csv')
    args = parser.parse_args()

    fichiers = sorted(Path(args.raw).glob('base-flux-mobilite-residentielle-*.csv'))
    if not fichiers:
        raise SystemExit(f"Aucun fichier base-flux-mobilite-residentielle-*.csv dans {args.raw}")

    print("Lecture des fichiers INSEE...")
    liste_df = []
    for f in fichiers:
        liste_df.append(lire_annee(f))

    #On fusionne...
    print("Fusion...")
    df_final = pd.concat(liste_df, ignore_index=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(args.out, sep=';', index=False)

    nb = f"{len(df_final):,}".replace(',', ' ')
    print(f"Terminé, {nb} flux sauvegardés dans {args.out}")


if __name__ == '__main__':
    main()
