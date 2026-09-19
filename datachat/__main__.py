"""Interface en ligne de commande.

    python -m datachat --data data/flux_migratoire_triee.csv
    python -m datachat --data data/flux_migratoire_triee.csv -q "Où partent les Parisiens ?"
"""

from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from datachat.agent import DataChat
from datachat.data_loader import load_flux


def afficher(reponse, montrer_plan: bool) -> None:
    if montrer_plan and reponse.plan is not None:
        print("\n[plan]", json.dumps(reponse.plan.model_dump(exclude_none=True), ensure_ascii=False))
    print("\n" + reponse.texte)
    if reponse.graphique:
        print(f"\n📊 Graphique : {reponse.graphique}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DataChat-FR : questions en français sur les flux INSEE")
    parser.add_argument("--data", default="data/flux_migratoire_triee.csv", help="CSV des flux préparés")
    parser.add_argument("-q", "--question", help="Poser une seule question puis quitter")
    parser.add_argument("--plan", action="store_true", help="Afficher le plan JSON généré par le LLM")
    args = parser.parse_args()

    load_dotenv()
    print("Chargement des données...")
    agent = DataChat(load_flux(args.data))
    print(f"✅ {len(agent.flux):,} flux chargés ({agent.annees[0]}-{agent.annees[-1]})".replace(",", " "))

    if args.question:
        afficher(agent.ask(args.question), args.plan)
        return

    print("Pose ta question (ou 'q' pour quitter).")
    while True:
        try:
            question = input("\n❓ ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"q", "quit", "exit"}:
            break
        if question:
            afficher(agent.ask(question), args.plan)


if __name__ == "__main__":
    main()
