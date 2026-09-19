"""Les seules opérations que l'agent a le droit d'exécuter.

Chaque opération est une fonction Pandas écrite à la main et testée.
Le plan du LLM sert uniquement à choisir la fonction et ses paramètres :
aucun code généré n'est jamais exécuté (pas d'eval / exec).
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from datachat.data_loader import RepertoireCommunes
from datachat.plan import Plan, PlanInvalide


def _annee_unique(df: pd.DataFrame, plan: Plan) -> int:
    annees = sorted(df["annee"].unique())
    annee = plan.annee or annees[-1]  # par défaut : le millésime le plus récent
    if annee not in annees:
        raise PlanInvalide(f"Année {annee} indisponible (années disponibles : {annees}).")
    return int(annee)


def _annees(df: pd.DataFrame, plan: Plan) -> list[int]:
    disponibles = sorted(int(a) for a in df["annee"].unique())
    demandees = plan.annees or ([plan.annee] if plan.annee else disponibles)
    retenues = [a for a in demandees if a in disponibles]
    if not retenues:
        raise PlanInvalide(f"Aucune année demandée n'est disponible ({disponibles}).")
    return retenues


def _commune(rep: RepertoireCommunes, nom: str | None, plan: Plan):
    if not nom:
        raise PlanInvalide(f"L'opération {plan.operation} nécessite une commune.")
    return rep.resoudre(nom, plan.departement)


def top_destinations(df: pd.DataFrame, rep: RepertoireCommunes, plan: Plan) -> pd.DataFrame:
    """Où partent les habitants qui quittent une commune ?"""
    commune, annee = _commune(rep, plan.commune, plan), _annee_unique(df, plan)
    sel = df[(df["annee"] == annee) & (df["code_orig"] == commune.code)]
    res = (
        sel.groupby(["code_dest", "nom_dest"], as_index=False)["flux"].sum()
        .nlargest(plan.n, "flux")
        .rename(columns={"code_dest": "code", "nom_dest": "commune"})
    )
    res.attrs["contexte"] = f"Départs depuis {commune.nom} en {annee}"
    return res.reset_index(drop=True)


def top_origines(df: pd.DataFrame, rep: RepertoireCommunes, plan: Plan) -> pd.DataFrame:
    """D'où viennent les nouveaux habitants d'une commune ?"""
    commune, annee = _commune(rep, plan.commune, plan), _annee_unique(df, plan)
    sel = df[(df["annee"] == annee) & (df["code_dest"] == commune.code)]
    res = (
        sel.groupby(["code_orig", "nom_orig"], as_index=False)["flux"].sum()
        .nlargest(plan.n, "flux")
        .rename(columns={"code_orig": "code", "nom_orig": "commune"})
    )
    res.attrs["contexte"] = f"Arrivées à {commune.nom} en {annee}"
    return res.reset_index(drop=True)


def solde_migratoire(df: pd.DataFrame, rep: RepertoireCommunes, plan: Plan) -> pd.DataFrame:
    """Arrivées, départs et solde (arrivées - départs) d'une commune par année."""
    commune, annees = _commune(rep, plan.commune, plan), _annees(df, plan)
    sel = df[df["annee"].isin(annees)]
    arrivees = sel[sel["code_dest"] == commune.code].groupby("annee")["flux"].sum()
    departs = sel[sel["code_orig"] == commune.code].groupby("annee")["flux"].sum()
    res = pd.DataFrame({"arrivees": arrivees, "departs": departs}).reindex(annees).fillna(0)
    res["solde"] = res["arrivees"] - res["departs"]
    res = res.rename_axis("annee").reset_index()
    res.attrs["contexte"] = f"Solde migratoire de {commune.nom}"
    return res


def flux_entre(df: pd.DataFrame, rep: RepertoireCommunes, plan: Plan) -> pd.DataFrame:
    """Flux dans les deux sens entre deux communes, par année."""
    a = _commune(rep, plan.commune, plan)
    b = _commune(rep, plan.commune_b, plan.model_copy(update={"departement": None}))
    annees = _annees(df, plan)
    sel = df[df["annee"].isin(annees)]
    a_vers_b = sel[(sel["code_orig"] == a.code) & (sel["code_dest"] == b.code)].groupby("annee")["flux"].sum()
    b_vers_a = sel[(sel["code_orig"] == b.code) & (sel["code_dest"] == a.code)].groupby("annee")["flux"].sum()
    res = pd.DataFrame({f"{a.nom} → {b.nom}": a_vers_b, f"{b.nom} → {a.nom}": b_vers_a})
    res = res.reindex(annees).fillna(0).rename_axis("annee").reset_index()
    res.attrs["contexte"] = f"Flux entre {a.nom} et {b.nom}"
    return res


def classement_solde(df: pd.DataFrame, rep: RepertoireCommunes, plan: Plan) -> pd.DataFrame:
    """Communes qui gagnent (ou perdent) le plus d'habitants par mobilité résidentielle."""
    annee = _annee_unique(df, plan)
    sel = df[df["annee"] == annee]
    if plan.departement:
        dep = str(plan.departement).zfill(2)
        sel_dest = sel[sel["code_dest"].str.startswith(dep)]
        sel_orig = sel[sel["code_orig"].str.startswith(dep)]
    else:
        sel_dest = sel_orig = sel
    arrivees = sel_dest.groupby(["code_dest", "nom_dest"])["flux"].sum()
    departs = sel_orig.groupby(["code_orig", "nom_orig"])["flux"].sum()
    arrivees.index.names = departs.index.names = ["code", "commune"]
    res = pd.DataFrame({"arrivees": arrivees, "departs": departs}).fillna(0)
    res["solde"] = res["arrivees"] - res["departs"]
    res = res.reset_index()
    res = res.nlargest(plan.n, "solde") if plan.sens == "gains" else res.nsmallest(plan.n, "solde")
    # Homonymes (ex. Saint-Denis 93 et 974) : on ajoute le département au nom
    doublons = res["commune"].duplicated(keep=False)
    dep = res["code"].map(lambda c: c[:3] if c.startswith("97") else c[:2])
    res.loc[doublons, "commune"] = res.loc[doublons, "commune"] + " (" + dep[doublons] + ")"
    perimetre = f" (département {plan.departement})" if plan.departement else ""
    res.attrs["contexte"] = f"Communes avec le solde le plus {'positif' if plan.sens == 'gains' else 'négatif'} en {annee}{perimetre}"
    return res.reset_index(drop=True)


OPERATIONS: dict[str, Callable[[pd.DataFrame, RepertoireCommunes, Plan], pd.DataFrame]] = {
    "top_destinations": top_destinations,
    "top_origines": top_origines,
    "solde_migratoire": solde_migratoire,
    "flux_entre": flux_entre,
    "classement_solde": classement_solde,
}
