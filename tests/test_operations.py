import pytest

from datachat.data_loader import CommuneIntrouvable, normaliser_nom
from datachat.operations import (
    classement_solde,
    flux_entre,
    solde_migratoire,
    top_destinations,
    top_origines,
)
from datachat.plan import Plan, PlanInvalide


def test_arrondissements_regroupes(flux):
    assert "75101" not in set(flux["code_orig"]) | set(flux["code_dest"])
    # 100 + 50 depuis deux arrondissements de Paris vers Lyon -> un seul flux de 150
    ligne = flux[(flux["code_orig"] == "75056") & (flux["code_dest"] == "69123")]
    assert ligne["flux"].tolist() == [150]
    # les déménagements internes (entre arrondissements ou dans la même commune) disparaissent
    assert (flux["code_orig"] != flux["code_dest"]).all()


def test_normalisation_des_noms():
    assert normaliser_nom("Saint-Étienne") == "saint etienne"
    assert normaliser_nom("  L'Haÿ-les-Roses ") == "l hay les roses"


def test_resolution_commune(repertoire):
    assert repertoire.resoudre("paris").code == "75056"
    assert repertoire.resoudre("CERGY").code == "95127"
    # homonymes : la plus importante par défaut, sinon le département demandé
    assert repertoire.resoudre("Saint-Denis", departement="974").code == "97411"
    with pytest.raises(CommuneIntrouvable):
        repertoire.resoudre("Atlantide")


def test_top_destinations(flux, repertoire):
    res = top_destinations(flux, repertoire, Plan(operation="top_destinations", commune="Paris", annee=2018))
    assert res["commune"].tolist() == ["Lyon", "Nantes", "Cergy"]
    assert res["flux"].tolist() == [150, 80, 40]


def test_annee_par_defaut_la_plus_recente(flux, repertoire):
    res = top_destinations(flux, repertoire, Plan(operation="top_destinations", commune="Paris"))
    assert res.attrs["contexte"].endswith("2020")


def test_top_origines(flux, repertoire):
    res = top_origines(flux, repertoire, Plan(operation="top_origines", commune="Cergy", annee=2020))
    assert res["commune"].tolist() == ["Saint-Denis"]


def test_solde_migratoire(flux, repertoire):
    res = solde_migratoire(flux, repertoire, Plan(operation="solde_migratoire", commune="Paris"))
    r2018 = res[res["annee"] == 2018].iloc[0]
    assert (r2018["arrivees"], r2018["departs"], r2018["solde"]) == (50, 270, -220)


def test_flux_entre(flux, repertoire):
    res = flux_entre(flux, repertoire, Plan(operation="flux_entre", commune="Paris", commune_b="Nantes"))
    assert res.columns.tolist() == ["annee", "Paris → Nantes", "Nantes → Paris"]
    assert res.set_index("annee").loc[2020].tolist() == [150, 20]


def test_classement_solde(flux, repertoire):
    gains = classement_solde(flux, repertoire, Plan(operation="classement_solde", annee=2020, n=2))
    assert gains.iloc[0]["commune"] == "Nantes"  # +150 - 20 = +130
    pertes = classement_solde(flux, repertoire, Plan(operation="classement_solde", annee=2020, sens="pertes", n=1))
    assert pertes.iloc[0]["commune"] == "Paris"


def test_annee_indisponible(flux, repertoire):
    with pytest.raises(PlanInvalide):
        top_destinations(flux, repertoire, Plan(operation="top_destinations", commune="Paris", annee=1990))
