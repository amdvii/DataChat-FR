"""Tests de l'agent complet avec un faux LLM (aucun appel à OpenAI)."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from datachat.agent import DataChat
from datachat.plan import extraire_json


def agent(flux, tmp_path, reponses):
    return DataChat(flux, llm=FakeListChatModel(responses=reponses), dossier_graphiques=tmp_path)


def test_pipeline_complet(flux, tmp_path):
    plan = '{"operation": "top_destinations", "commune": "Paris", "annee": 2018, "titre": "Départs de Paris 2018"}'
    rep = agent(flux, tmp_path, [plan, "En 2018, Lyon est la première destination."]).ask("Où partent les Parisiens ?")
    assert rep.plan.operation == "top_destinations"
    assert rep.resultat["commune"].iloc[0] == "Lyon"
    assert rep.graphique is not None and rep.graphique.exists()
    assert rep.texte.startswith("En 2018")


def test_le_llm_peut_corriger_un_plan_invalide(flux, tmp_path):
    mauvais = '{"operation": "supprimer_tout"}'
    bon = '```json\n{"operation": "solde_migratoire", "commune": "Nantes", "graphique": "courbe"}\n```'
    rep = agent(flux, tmp_path, [mauvais, bon, "Synthèse."]).ask("Nantes attire-t-elle ?")
    assert rep.plan.operation == "solde_migratoire"
    assert len(rep.erreurs) == 1


def test_question_hors_perimetre(flux, tmp_path):
    plan = '{"operation": "hors_perimetre", "raison": "Pas de données de prix."}'
    rep = agent(flux, tmp_path, [plan]).ask("Prix du m2 à Nantes ?")
    assert "Pas de données de prix" in rep.texte
    assert rep.resultat is None


def test_commune_inconnue(flux, tmp_path):
    plan = '{"operation": "top_origines", "commune": "Atlantide"}'
    rep = agent(flux, tmp_path, [plan]).ask("Qui arrive à Atlantide ?")
    assert "introuvable" in rep.texte


def test_extraire_json_avec_texte_autour():
    assert extraire_json('Voici le plan : {"operation": "classement_solde"} !') == {"operation": "classement_solde"}
