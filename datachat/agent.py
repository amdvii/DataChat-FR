import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from datachat import visualizer
from datachat.data_loader import CommuneIntrouvable, RepertoireCommunes
from datachat.operations import OPERATIONS
from datachat.plan import Plan, PlanInvalide, extraire_json
from datachat.prompts import PROMPT_PLANIFICATION, PROMPT_SYNTHESE

# Le pipeline en 5 étapes pour chaque question :
# 1. on reçoit la question en français
# 2. le LLM génère un plan d'exécution JSON        -> _generate_plan
# 3. on exécute le plan avec pandas (sécurisé)     -> _execute_plan
# 4. on génère le graphique automatiquement        -> visualizer.tracer
# 5. le LLM rédige la réponse finale en français   -> _synthesize


# ce que l'agent renvoie pour chaque question
class Answer:
    def __init__(self, question, texte, plan=None, resultat=None, graphique=None, erreurs=None):
        self.question = question
        self.texte = texte
        self.plan = plan
        self.resultat = resultat
        self.graphique = graphique
        self.erreurs = erreurs or []


# LLM par défaut : gpt-4o-mini d'OpenAI (la clé est lue dans le .env)
def creer_llm():
    from langchain_openai import ChatOpenAI

    if not os.getenv('OPENAI_API_KEY'):
        raise RuntimeError("OPENAI_API_KEY manquante : copie .env.example en .env et mets ta clé dedans.")
    return ChatOpenAI(model=os.getenv('DATACHAT_MODEL', 'gpt-4o-mini'), temperature=0)


class DataChat:
    # on peut passer n'importe quel modèle LangChain dans llm (OpenAI par défaut, mais aussi Ollama etc)
    def __init__(self, flux, llm=None, dossier_graphiques='outputs/charts', max_tentatives=2):
        self.flux = flux
        self.llm = llm or creer_llm()
        self.repertoire = RepertoireCommunes(flux)
        self.dossier_graphiques = Path(dossier_graphiques)
        self.max_tentatives = max_tentatives
        self.annees = sorted(int(a) for a in flux['annee'].unique())

    def ask(self, question):
        erreurs = []

        #étape 2 : le plan
        try:
            plan = self._generate_plan(question, erreurs)
        except PlanInvalide as e:
            return Answer(question, f"Je n'ai pas réussi à comprendre la demande ({e}).", erreurs=erreurs)

        if plan.operation == 'hors_perimetre':
            raison = plan.raison or "La question ne porte pas sur les flux de mobilité résidentielle."
            return Answer(question, f"Je ne peux pas répondre avec ces données : {raison}", plan=plan)

        #étape 3 : exécution
        try:
            resultat = self._execute_plan(plan)
        except (PlanInvalide, CommuneIntrouvable) as e:
            return Answer(question, str(e), plan=plan, erreurs=erreurs)

        if resultat.empty:
            return Answer(question, "Aucun flux ne correspond à cette demande dans les données.", plan, resultat)

        #étape 4 : graphique
        titre = plan.titre or resultat.attrs.get('contexte', 'DataChat-FR')
        graphique = visualizer.tracer(resultat, plan.graphique, titre, self.dossier_graphiques)

        #étape 5 : réponse en français
        texte = self._synthesize(question, resultat)
        return Answer(question, texte, plan, resultat, graphique, erreurs)

    # On demande au LLM un plan JSON puis on le vérifie avec pydantic.
    # Si le plan est invalide, on renvoie l'erreur au LLM pour qu'il se corrige
    # (c'est une boucle de correction simple, typique des agents)
    def _generate_plan(self, question, erreurs=None):
        if erreurs is None:
            erreurs = []

        periode = f"{self.annees[0]}-{self.annees[-1]}"
        messages = [
            SystemMessage(content=PROMPT_PLANIFICATION.format(annees=periode)),
            HumanMessage(content=question),
        ]

        for tentative in range(self.max_tentatives):
            reponse = self.llm.invoke(messages).content
            try:
                return Plan.model_validate(extraire_json(reponse))
            except (PlanInvalide, ValidationError) as e:
                erreurs.append(str(e))
                #on garde la mauvaise réponse dans l'historique + on lui dit ce qui va pas
                messages.append(AIMessage(content=reponse))
                messages.append(HumanMessage(content=f"Ton plan est invalide : {e}. Renvoie uniquement un JSON corrigé."))

        raise PlanInvalide(erreurs[-1])

    # on appelle la fonction pandas qui correspond au plan (seulement celles de OPERATIONS)
    def _execute_plan(self, plan):
        operation = OPERATIONS.get(plan.operation)
        if operation is None:
            raise PlanInvalide(f"Opération non autorisée : {plan.operation}")
        return operation(self.flux, self.repertoire, plan)

    # le LLM rédige la réponse à partir du tableau de résultats UNIQUEMENT (pour limiter les hallucinations)
    def _synthesize(self, question, resultat):
        tableau = resultat.drop(columns=['code'], errors='ignore').head(30).round(0).to_string(index=False)
        prompt = PROMPT_SYNTHESE.format(question=question, contexte=resultat.attrs.get('contexte', ''), tableau=tableau)
        return self.llm.invoke([HumanMessage(content=prompt)]).content.strip()
