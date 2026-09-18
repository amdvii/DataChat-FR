# Exemples de questions

Une question par opération disponible :

| Question | Opération choisie par le LLM |
|---|---|
| Où partent les Parisiens en 2021 ? | `top_destinations` |
| D'où viennent les nouveaux habitants de Nantes ? | `top_origines` |
| Est-ce que Lyon a perdu des habitants depuis le Covid ? | `solde_migratoire` |
| Combien de personnes passent de Paris à Bordeaux chaque année ? | `flux_entre` |
| Quelles communes du Val-d'Oise attirent le plus en 2022 ? | `classement_solde` (sens `gains`, département `95`) |
| Quelles villes perdent le plus d'habitants ? | `classement_solde` (sens `pertes`) |
| Quel est le prix de l'immobilier à Nantes ? | `hors_perimetre` (refus expliqué) |

Pour voir le plan JSON généré à chaque question :

```bash
python -m datachat --plan
```
