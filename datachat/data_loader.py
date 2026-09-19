"""Chargement et préparation des flux de mobilité résidentielle INSEE.

Le fichier attendu est celui produit par l'ETL d'UrbanFlows-FR
(``flux_migratoire_triee.csv``, séparateur ``;``) ou par
``scripts/prepare_insee.py``, avec les colonnes :
``annee, code_orig, nom_orig, code_dest, nom_dest, flux``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

COLONNES = ["annee", "code_orig", "nom_orig", "code_dest", "nom_dest", "flux"]

# Paris, Lyon et Marseille sont découpées en arrondissements municipaux par
# l'INSEE. On les regroupe sous le code de la commune pour pouvoir poser des
# questions sur "Paris" ou "Lyon" directement.
ARRONDISSEMENTS = {
    "Paris": ("75056", lambda c: c.startswith("751") and len(c) == 5),
    "Lyon": ("69123", lambda c: c.startswith("6938") and len(c) == 5),
    "Marseille": ("13055", lambda c: c.startswith("132") and len(c) == 5),
}


def normaliser_nom(nom: str) -> str:
    """Minuscules, sans accents, tirets et apostrophes remplacés par des espaces."""
    nom = unicodedata.normalize("NFKD", str(nom))
    nom = "".join(ch for ch in nom if not unicodedata.combining(ch))
    for ch in "-'’":
        nom = nom.replace(ch, " ")
    return " ".join(nom.lower().split())


def _regrouper_arrondissements(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for ville, (code_ville, est_arrondissement) in ARRONDISSEMENTS.items():
        for cote in ("orig", "dest"):
            masque = df[f"code_{cote}"].map(est_arrondissement)
            df.loc[masque, f"code_{cote}"] = code_ville
            df.loc[masque, f"nom_{cote}"] = ville
    # Un déménagement entre deux arrondissements devient un flux interne : on l'exclut.
    df = df[df["code_orig"] != df["code_dest"]]
    return df.groupby(
        ["annee", "code_orig", "nom_orig", "code_dest", "nom_dest"], as_index=False
    )["flux"].sum()


def preparer_flux(df: pd.DataFrame, regrouper_arrondissements: bool = True) -> pd.DataFrame:
    """Vérifie le schéma, type les colonnes et applique un nettoyage minimal."""
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le fichier de flux : {manquantes}")

    df = df[COLONNES].copy()
    df["annee"] = df["annee"].astype(int)
    for col in ("code_orig", "code_dest"):
        df[col] = df[col].astype(str).str.strip().str.zfill(5)
    df["flux"] = pd.to_numeric(df["flux"], errors="coerce")
    df = df.dropna(subset=["flux"])
    df = df[(df["flux"] > 0) & (df["code_orig"] != df["code_dest"])]

    if regrouper_arrondissements:
        df = _regrouper_arrondissements(df)
    return df.reset_index(drop=True)


def load_flux(chemin: str | Path, regrouper_arrondissements: bool = True) -> pd.DataFrame:
    """Charge le CSV des flux et le prépare pour l'agent."""
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {chemin}. Voir data/README.md pour préparer les données."
        )
    df = pd.read_csv(chemin, sep=";", dtype={"code_orig": str, "code_dest": str})
    return preparer_flux(df, regrouper_arrondissements)


@dataclass(frozen=True)
class Commune:
    code: str
    nom: str


class CommuneIntrouvable(ValueError):
    pass


class RepertoireCommunes:
    """Résout un nom de commune tapé par l'utilisateur ("saint etienne",
    "Cergy", "Paris") en code INSEE, sans tenir compte des accents ni des tirets."""

    def __init__(self, df: pd.DataFrame):
        orig = df[["code_orig", "nom_orig"]].set_axis(["code", "nom"], axis=1)
        dest = df[["code_dest", "nom_dest"]].set_axis(["code", "nom"], axis=1)
        communes = pd.concat([orig, dest]).drop_duplicates("code")
        poids = df.groupby("code_orig")["flux"].sum().add(
            df.groupby("code_dest")["flux"].sum(), fill_value=0
        )
        communes["poids"] = communes["code"].map(poids).fillna(0)
        communes["cle"] = communes["nom"].map(normaliser_nom)
        self._communes = communes.sort_values("poids", ascending=False)

    def resoudre(self, nom: str, departement: str | None = None) -> Commune:
        cle = normaliser_nom(nom)
        candidats = self._communes[self._communes["cle"] == cle]
        if departement:
            candidats = candidats[candidats["code"].str.startswith(str(departement).zfill(2))]
        if candidats.empty:
            proches = self._communes[self._communes["cle"].str.startswith(cle)]
            suggestion = ", ".join(proches["nom"].head(3)) or "aucune"
            raise CommuneIntrouvable(
                f"Commune « {nom} » introuvable dans les données (suggestions : {suggestion})."
            )
        # Plusieurs homonymes (ex. Saint-Denis 93 / 974) : on garde la plus importante,
        # sauf si le plan précise le département.
        ligne = candidats.iloc[0]
        return Commune(code=ligne["code"], nom=ligne["nom"])
