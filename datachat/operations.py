import pandas as pd

from datachat.plan import PlanInvalide

# Les seules opérations que l'agent a le droit de lancer.
# Chaque fonction est écrite à la main et testée, le plan du LLM sert juste
# à choisir laquelle appeler (pas de eval / exec)


# les fcts utilitaires

# si l'année n'est pas précisée on prend la plus récente
def choisir_annee(df, plan):
    annees = sorted(df['annee'].unique())
    annee = plan.annee or annees[-1]
    if annee not in annees:
        raise PlanInvalide(f"Année {annee} indisponible (années disponibles : {annees}).")
    return int(annee)


def choisir_annees(df, plan):
    disponibles = sorted(int(a) for a in df['annee'].unique())
    if plan.annees:
        demandees = plan.annees
    elif plan.annee:
        demandees = [plan.annee]
    else:
        demandees = disponibles #pas d'année précisée = toute la période

    annees = [a for a in demandees if a in disponibles]
    if not annees:
        raise PlanInvalide(f"Aucune année demandée n'est disponible ({disponibles}).")
    return annees


def trouver_commune(rep, nom, plan):
    if not nom:
        raise PlanInvalide(f"L'opération {plan.operation} nécessite une commune.")
    return rep.resoudre(nom, plan.departement)


# les opérations

# où partent les habitants qui quittent une commune ?
def top_destinations(df, rep, plan):
    commune = trouver_commune(rep, plan.commune, plan)
    annee = choisir_annee(df, plan)

    sel = df[(df['annee'] == annee) & (df['code_orig'] == commune.code)]
    res = sel.groupby(['code_dest', 'nom_dest'], as_index=False)['flux'].sum()
    res = res.nlargest(plan.n, 'flux')
    res.columns = ['code', 'commune', 'flux']

    res.attrs['contexte'] = f"Départs depuis {commune.nom} en {annee}"
    return res.reset_index(drop=True)


# d'où viennent les nouveaux habitants d'une commune ?
def top_origines(df, rep, plan):
    commune = trouver_commune(rep, plan.commune, plan)
    annee = choisir_annee(df, plan)

    sel = df[(df['annee'] == annee) & (df['code_dest'] == commune.code)]
    res = sel.groupby(['code_orig', 'nom_orig'], as_index=False)['flux'].sum()
    res = res.nlargest(plan.n, 'flux')
    res.columns = ['code', 'commune', 'flux']

    res.attrs['contexte'] = f"Arrivées à {commune.nom} en {annee}"
    return res.reset_index(drop=True)


# arrivées, départs et solde (arrivées - départs) d'une commune pour chaque année
def solde_migratoire(df, rep, plan):
    commune = trouver_commune(rep, plan.commune, plan)
    annees = choisir_annees(df, plan)

    sel = df[df['annee'].isin(annees)]
    arrivees = sel[sel['code_dest'] == commune.code].groupby('annee')['flux'].sum()
    departs = sel[sel['code_orig'] == commune.code].groupby('annee')['flux'].sum()

    res = pd.DataFrame({'arrivees': arrivees, 'departs': departs}).reindex(annees).fillna(0)
    res['solde'] = res['arrivees'] - res['departs']
    res = res.rename_axis('annee').reset_index()

    res.attrs['contexte'] = f"Solde migratoire de {commune.nom}"
    return res


# flux dans les 2 sens entre 2 communes, par année
def flux_entre(df, rep, plan):
    a = trouver_commune(rep, plan.commune, plan)
    b = trouver_commune(rep, plan.commune_b, plan.model_copy(update={'departement': None})) #le département du plan ne concerne que la 1ere commune
    annees = choisir_annees(df, plan)

    sel = df[df['annee'].isin(annees)]
    a_vers_b = sel[(sel['code_orig'] == a.code) & (sel['code_dest'] == b.code)].groupby('annee')['flux'].sum()
    b_vers_a = sel[(sel['code_orig'] == b.code) & (sel['code_dest'] == a.code)].groupby('annee')['flux'].sum()

    res = pd.DataFrame({f"{a.nom} → {b.nom}": a_vers_b, f"{b.nom} → {a.nom}": b_vers_a})
    res = res.reindex(annees).fillna(0).rename_axis('annee').reset_index()

    res.attrs['contexte'] = f"Flux entre {a.nom} et {b.nom}"
    return res


# les communes qui gagnent (ou perdent) le plus d'habitants
def classement_solde(df, rep, plan):
    annee = choisir_annee(df, plan)
    sel = df[df['annee'] == annee]

    #filtre sur un département si demandé
    if plan.departement:
        dep = str(plan.departement).zfill(2)
        sel_dest = sel[sel['code_dest'].str.startswith(dep)]
        sel_orig = sel[sel['code_orig'].str.startswith(dep)]
    else:
        sel_dest = sel
        sel_orig = sel

    arrivees = sel_dest.groupby(['code_dest', 'nom_dest'])['flux'].sum()
    departs = sel_orig.groupby(['code_orig', 'nom_orig'])['flux'].sum()
    arrivees.index.names = ['code', 'commune']
    departs.index.names = ['code', 'commune']

    #arrivées - départs
    res = pd.DataFrame({'arrivees': arrivees, 'departs': departs}).fillna(0)
    res['solde'] = res['arrivees'] - res['departs']
    res = res.reset_index()

    if plan.sens == 'gains':
        res = res.nlargest(plan.n, 'solde')
    else:
        res = res.nsmallest(plan.n, 'solde')

    #pour les homonymes (ex : Saint-Denis 93 et 974) on rajoute le département à côté du nom
    doublons = res['commune'].duplicated(keep=False)
    dep = res['code'].apply(lambda c: c[:3] if c.startswith('97') else c[:2]) #les DOM ont un code sur 3 chiffres
    res.loc[doublons, 'commune'] = res.loc[doublons, 'commune'] + ' (' + dep[doublons] + ')'

    perimetre = f" (département {plan.departement})" if plan.departement else ''
    mot = 'positif' if plan.sens == 'gains' else 'négatif'
    res.attrs['contexte'] = f"Communes avec le solde le plus {mot} en {annee}{perimetre}"
    return res.reset_index(drop=True)


OPERATIONS = {
    'top_destinations': top_destinations,
    'top_origines': top_origines,
    'solde_migratoire': solde_migratoire,
    'flux_entre': flux_entre,
    'classement_solde': classement_solde,
}
