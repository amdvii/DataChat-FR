"""L'agent DataChat-FR.

Pipeline en 5 étapes pour chaque question :
1. réception de la question en français
2. le LLM génère un plan d'exécution JSON        -> _generate_plan
3. exécution Pandas sécurisée du plan            -> _execute_plan
4. génération automatique d'un graphique         -> visualizer.tracer
5. synthèse finale en français par le LLM        -> _synthesize
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from datachat import visualizer
from datachat.data_loader import CommuneIntrouvable, RepertoireCommunes
from datachat.operations import OPERATIONS
from datachat.plan import Plan, PlanInvalide, extraire_json
from datachat.prompts import PROMPT_PLANIFICATION, PROMPT_SYNTHESE


@dataclass
class Answer:
    question: str
    texte: str
    plan: Plan | None = None
    resultat: pd.DataFrame | None = None
    graphique: Path | None = None
    erreurs: list[str] = field(default_factory=list)


def creer_llm() -> BaseChatModel:
    """LLM par défaut : OpenAI gpt-4o-mini (clé lue dans la variable OPENAI_API_KEY)."""
    from langchain_openai import ChatOpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY manquante : copie .env.example en .env et renseigne ta clé.")
    return ChatOpenAI(model=os.getenv("DATACHAT_MODEL", "gpt-4o-mini"), temperature=0)


class DataChat:
    """Agent conversationnel sur les flux de mobilité résidentielle INSEE.

    N'importe quel modèle de chat LangChain peut être injecté via ``llm``
    (OpenAI par défaut, mais aussi Ollama, Mistral, etc.).
    """

    def __init__(
        self,
        flux: pd.DataFrame,
        llm: BaseChatModel | None = None,
        dossier_graphiques: str | Path = "outputs/charts",
        max_tentatives: int = 2,
    ):
        self.flux = flux
        self.llm = llm or creer_llm()
        self.repertoire = RepertoireCommunes(flux)
        self.dossier_graphiques = Path(dossier_graphiques)
        self.max_tentatives = max_tentatives
        self.annees = sorted(int(a) for a in flux["annee"].unique())

    # ------------------------------------------------------------------ API
    def ask(self, question: str) -> Answer:
        erreurs: list[str] = []

        # Étape 2 : planification (avec une nouvelle tentative si le plan est invalide)
        try:
            plan = self._generate_plan(question, erreurs)
        except PlanInvalide as exc:
            return Answer(question, f"Je n'ai pas réussi à comprendre la demande ({exc}).", erreurs=erreurs)

        if plan.operation == "hors_perimetre":
            raison = plan.raison or "La question ne porte pas sur les flux de mobilité résidentielle."
            return Answer(question, f"Je ne peux pas répondre avec ces données : {raison}", plan=plan)

        # Étape 3 : exécution
        try:
            resultat = self._execute_plan(plan)
        except (PlanInvalide, CommuneIntrouvable) as exc:
            return Answer(question, str(exc), plan=plan, erreurs=erreurs)

        if resultat.empty:
            return Answer(question, "Aucun flux ne correspond à cette demande dans les données.", plan, resultat)

        # Étape 4 : graphique
        titre = plan.titre or resultat.attrs.get("contexte", "DataChat-FR")
        graphique = visualizer.tracer(resultat, plan.graphique, titre, self.dossier_graphiques)

        # Étape 5 : synthèse
        texte = self._synthesize(question, resultat)
        return Answer(question, texte, plan, resultat, graphique, erreurs)

    # ------------------------------------------------------------ étapes
    def _generate_plan(self, question: str, erreurs: list[str] | None = None) -> Plan:
        """Demande au LLM un plan JSON, puis le valide avec Pydantic.

        Si le JSON est invalide, on renvoie l'erreur au LLM pour qu'il se corrige
        (boucle de correction simple, typique des agents).
        """
        erreurs = erreurs if erreurs is not None else []
        messages = [
            SystemMessage(content=PROMPT_PLANIFICATION.format(annees=f"{self.annees[0]}-{self.annees[-1]}")),
            HumanMessage(content=question),
        ]
        for _ in range(self.max_tentatives):
            reponse = self.llm.invoke(messages).content
            try:
                return Plan.model_validate(extraire_json(reponse))
            except (PlanInvalide, ValidationError) as exc:
                erreurs.append(str(exc))
                messages += [
                    AIMessage(content=reponse),
                    HumanMessage(content=f"Ton plan est invalide : {exc}. Renvoie uniquement un JSON corrigé."),
                ]
        raise PlanInvalide(erreurs[-1])

    def _execute_plan(self, plan: Plan) -> pd.DataFrame:
        """Exécute le plan en appelant une fonction Pandas de la liste blanche OPERATIONS."""
        operation = OPERATIONS.get(plan.operation)
        if operation is None:
            raise PlanInvalide(f"Opération non autorisée : {plan.operation}")
        return operation(self.flux, self.repertoire, plan)

    def _synthesize(self, question: str, resultat: pd.DataFrame) -> str:
        tableau = resultat.drop(columns=["code"], errors="ignore").head(30).round(0).to_string(index=False)
        prompt = PROMPT_SYNTHESE.format(
            question=question, contexte=resultat.attrs.get("contexte", ""), tableau=tableau
        )
        return self.llm.invoke([HumanMessage(content=prompt)]).content.strip()
