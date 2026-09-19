import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

# le LLM n'écrit jamais de code : il choisit juste une opération dans cette liste
# et remplit les paramètres, puis pydantic vérifie que tout est valide avant d'exécuter
Operation = Literal[
    'top_destinations',
    'top_origines',
    'solde_migratoire',
    'flux_entre',
    'classement_solde',
    'hors_perimetre',
]


class Plan(BaseModel):
    operation: Operation
    commune: Optional[str] = None
    commune_b: Optional[str] = None
    departement: Optional[str] = None
    annee: Optional[int] = None
    annees: Optional[list[int]] = None
    n: int = Field(10, ge=1, le=30) #entre 1 et 30 résultats max
    sens: Literal['gains', 'pertes'] = 'gains'
    graphique: Literal['barres', 'courbe', 'aucun'] = 'barres'
    titre: Optional[str] = None
    raison: Optional[str] = None #rempli seulement si la question est hors sujet


class PlanInvalide(ValueError):
    pass


# le LLM renvoie parfois le json entouré de ```json ... ``` ou avec du texte autour,
# on récupère juste ce qu'il y a entre la 1ere { et la dernière }
def extraire_json(texte):
    texte = re.sub(r'```(?:json)?', '', texte).strip()
    debut = texte.find('{')
    fin = texte.rfind('}')
    if debut == -1 or fin == -1:
        raise PlanInvalide(f"Aucun objet JSON dans la réponse du LLM : {texte[:200]!r}")

    try:
        return json.loads(texte[debut:fin + 1])
    except json.JSONDecodeError as e:
        raise PlanInvalide(f"JSON mal formé : {e}") from e
