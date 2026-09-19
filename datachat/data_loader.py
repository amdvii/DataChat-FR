import unicodedata
from pathlib import Path

import pandas as pd

# même format que la sortie de l'ETL d'UrbanFlows-FR (flux_migratoire_triee.csv)
COLONNES = ['annee', 'code_orig', 'nom_orig', 'code_dest', 'nom_dest', 'flux']


# Paris, Lyon et Marseille sont découpées en arrondissements par l'INSEE,
# on les regroupe pour pouvoir poser des questions sur "Paris" directement
def regrouper_arrondissements(code):
    code = str(code)
    if code.startswith('751') and len(code) == 5: return ('75056', 'Paris')
    if code.startswith('6938') and len(code) == 5: return ('69123', 'Lyon')
    if code.startswith('132') and len(code) == 5: return ('13055', 'Marseille')
    return None


# minuscules + on enlève les accents, tirets et apostrophes
# (pour que "saint etienne" retrouve bien "Saint-Étienne")
def normaliser_nom(nom):
    nom = unicodedata.normalize('NFKD', str(nom))
    nom = ''.join(c for c in nom if not unicodedata.combining(c))
    for c in "-'’":
        nom = nom.replace(c, ' ')
    return ' '.join(nom.lower().split())


def preparer_flux(df, regrouper=True):
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le fichier de flux : {manquantes}")

    df = df[COLONNES].copy()
    df['annee'] = df['annee'].astype(int)
    df['code_orig'] = df['code_orig'].astype(str).str.strip().str.zfill(5)
    df['code_dest'] = df['code_dest'].astype(str).str.strip().str.zfill(5)
    df['flux'] = pd.to_numeric(df['flux'], errors='coerce')

    df = df.dropna(subset=['flux']) #on enlève les cases vides ou = à zéro
    df = df[df['flux'] > 0]
    df = df[df['code_orig'] != df['code_dest']] #les gens qui déménagent dans la même ville sont supprimés

    if regrouper:
        for cote in ['orig', 'dest']:
            nouveau = df[f'code_{cote}'].apply(regrouper_arrondissements)
            masque = nouveau.notna()
            df.loc[masque, f'code_{cote}'] = nouveau[masque].str[0]
            df.loc[masque, f'nom_{cote}'] = nouveau[masque].str[1]

        #un déménagement entre 2 arrondissements devient un flux interne, on le retire
        df = df[df['code_orig'] != df['code_dest']]
        df = df.groupby(['annee', 'code_orig', 'nom_orig', 'code_dest', 'nom_dest'], as_index=False)['flux'].sum()

    return df.reset_index(drop=True)


def load_flux(chemin, regrouper=True):
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}. Voir data/README.md pour préparer les données.")

    df = pd.read_csv(chemin, sep=';', dtype={'code_orig': str, 'code_dest': str})
    return preparer_flux(df, regrouper)


class Commune:
    def __init__(self, code, nom):
        self.code = code
        self.nom = nom


class CommuneIntrouvable(ValueError):
    pass


# sert à retrouver le code INSEE à partir du nom tapé par l'utilisateur
class RepertoireCommunes:
    def __init__(self, df):
        orig = df[['code_orig', 'nom_orig']].copy()
        orig.columns = ['code', 'nom']
        dest = df[['code_dest', 'nom_dest']].copy()
        dest.columns = ['code', 'nom']
        communes = pd.concat([orig, dest]).drop_duplicates('code')

        #poids = nb total de personnes qui arrivent ou partent (sert pour les homonymes)
        arrivees = df.groupby('code_dest')['flux'].sum()
        departs = df.groupby('code_orig')['flux'].sum()
        poids = departs.add(arrivees, fill_value=0)

        communes['poids'] = communes['code'].map(poids).fillna(0)
        communes['cle'] = communes['nom'].apply(normaliser_nom)
        self.communes = communes.sort_values('poids', ascending=False)

    def resoudre(self, nom, departement=None):
        cle = normaliser_nom(nom)
        candidats = self.communes[self.communes['cle'] == cle]
        if departement:
            candidats = candidats[candidats['code'].str.startswith(str(departement).zfill(2))]

        if candidats.empty:
            proches = self.communes[self.communes['cle'].str.startswith(cle)]
            suggestion = ', '.join(proches['nom'].head(3)) or 'aucune'
            raise CommuneIntrouvable(f"Commune « {nom} » introuvable dans les données (suggestions : {suggestion}).")

        # s'il y a plusieurs homonymes (ex : Saint-Denis 93 et 974) on prend la plus grosse,
        # sauf si le département est précisé dans le plan
        ligne = candidats.iloc[0]
        return Commune(ligne['code'], ligne['nom'])
