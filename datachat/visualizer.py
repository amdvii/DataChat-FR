import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg') #pas de fenêtre, on enregistre direct en png
import matplotlib.pyplot as plt

COULEURS = ['#C0392B', '#2C3E50', '#7F8C8D', '#E67E22'] #rouge, bleu nuit, gris, orange
LIBELLES = {'arrivees': 'Arrivées', 'departs': 'Départs', 'solde': 'Solde'}


# "Solde migratoire de Lyon" -> "solde_migratoire_de_lyon"
def nom_fichier(titre):
    nom = re.sub(r'[^a-z0-9]+', '_', titre.lower()).strip('_')[:80]
    return nom or 'graphique'


# trace le résultat et renvoie le chemin du png (ou None si pas de graphique)
def tracer(resultat, type_graphique, titre, dossier):
    if type_graphique == 'aucun' or resultat.empty:
        return None

    fig, ax = plt.subplots(figsize=(9, 5))

    if 'annee' in resultat.columns:
        #évolution dans le temps : une courbe par colonne
        colonnes = [c for c in resultat.columns if c != 'annee']
        for i, col in enumerate(colonnes):
            ax.plot(resultat['annee'], resultat[col], marker='o', label=LIBELLES.get(col, col), color=COULEURS[i % len(COULEURS)])
        ax.set_xticks(resultat['annee'])
        ax.axhline(0, color='black', linewidth=0.6)
        ax.set_ylabel("Nombre de personnes")
        ax.legend()
    else:
        #classement : barres horizontales, rouge si positif et bleu si négatif
        valeur = 'solde' if 'solde' in resultat.columns else 'flux'
        data = resultat.iloc[::-1] #le plus grand en haut
        couleurs = [COULEURS[0] if v >= 0 else COULEURS[1] for v in data[valeur]]
        ax.barh(data['commune'], data[valeur], color=couleurs)
        ax.set_xlabel("Solde migratoire" if valeur == 'solde' else "Nombre de personnes")

    ax.set_title(titre)
    ax.grid(True, alpha=0.3)
    fig.text(0.99, 0.01, "Source : INSEE, flux de mobilité résidentielle", ha='right', fontsize=8, color='grey')
    fig.tight_layout()

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{nom_fichier(titre)}.png"
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    return chemin
