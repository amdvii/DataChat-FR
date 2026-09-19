"""Schéma du plan d'exécution JSON produit par le LLM.

Le LLM ne génère jamais de code : il choisit une opération dans une liste
fermée et remplit ses paramètres. Pydantic valide le tout avant exécution.
"""

from __future__ import annotations

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

Operation = Literal[
    "top_destinations",
    "top_origines",
    "solde_migratoire",
    "flux_entre",
    "classement_solde",
    "hors_perimetre",
]


class Plan(BaseModel):
    operation: Operation
    commune: Optional[str] = None
    commune_b: Optional[str] = None
    departement: Optional[str] = None
    annee: Optional[int] = None
    annees: Optional[list[int]] = None
    n: int = Field(10, ge=1, le=30)
    sens: Literal["gains", "pertes"] = "gains"
    graphique: Literal["barres", "courbe", "aucun"] = "barres"
    titre: Optional[str] = None
    raison: Optional[str] = None


class PlanInvalide(ValueError):
    pass


def extraire_json(texte: str) -> dict:
    """Récupère l'objet JSON d'une réponse de LLM, même entouré de ```json ... ```."""
    texte = re.sub(r"```(?:json)?", "", texte).strip()
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut == -1 or fin == -1:
        raise PlanInvalide(f"Aucun objet JSON dans la réponse du LLM : {texte[:200]!r}")
    try:
        return json.loads(texte[debut : fin + 1])
    except json.JSONDecodeError as exc:
        raise PlanInvalide(f"JSON mal formé : {exc}") from exc
