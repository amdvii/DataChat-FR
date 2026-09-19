"""Génération automatique d'un graphique Matplotlib à partir d'un résultat."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pas de fenêtre : on enregistre directement en PNG
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

COULEURS = ["#C0392B", "#2C3E50", "#7F8C8D", "#E67E22"]
LIBELLES = {"arrivees": "Arrivées", "departs": "Départs", "solde": "Solde"}


def _nom_fichier(titre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", titre.lower()).strip("_")[:80] or "graphique"


def tracer(resultat: pd.DataFrame, type_graphique: str, titre: str, dossier: str | Path) -> Path | None:
    """Trace le résultat et renvoie le chemin du PNG (ou None si pas de graphique)."""
    if type_graphique == "aucun" or resultat.empty:
        return None

    fig, ax = plt.subplots(figsize=(9, 5))

    if "annee" in resultat.columns:
        # Séries temporelles : une courbe par colonne numérique
        for i, col in enumerate(c for c in resultat.columns if c != "annee"):
            ax.plot(resultat["annee"], resultat[col], marker="o", label=LIBELLES.get(col, col), color=COULEURS[i % len(COULEURS)])
        ax.set_xticks(resultat["annee"])
        ax.axhline(0, color="black", linewidth=0.6)
        ax.legend()
        ax.set_ylabel("Nombre de personnes")
    else:
        valeur = "solde" if "solde" in resultat.columns else "flux"
        data = resultat.iloc[::-1]  # le plus grand en haut
        couleurs = [COULEURS[0] if v >= 0 else COULEURS[1] for v in data[valeur]]
        ax.barh(data["commune"], data[valeur], color=couleurs)
        ax.set_xlabel("Solde migratoire" if valeur == "solde" else "Nombre de personnes")

    ax.set_title(titre)
    ax.grid(axis="both", alpha=0.3)
    fig.text(0.99, 0.01, "Source : INSEE, flux de mobilité résidentielle", ha="right", fontsize=8, color="grey")
    fig.tight_layout()

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{_nom_fichier(titre)}.png"
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    return chemin
