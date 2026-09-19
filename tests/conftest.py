import pandas as pd
import pytest

from datachat.data_loader import RepertoireCommunes, preparer_flux

# Petit jeu de données INVENTÉ pour tester le code sans télécharger les fichiers INSEE
LIGNES = [
    # annee, code_orig, nom_orig, code_dest, nom_dest, flux
    (2018, '75101', 'Paris 1er Arrondissement', '69381', 'Lyon 1er Arrondissement', 100),
    (2018, '75102', 'Paris 2e Arrondissement', '69381', 'Lyon 1er Arrondissement', 50),
    (2018, '75101', 'Paris 1er Arrondissement', '75102', 'Paris 2e Arrondissement', 999), #interne à Paris
    (2018, '75101', 'Paris 1er Arrondissement', '44109', 'Nantes', 80),
    (2018, '44109', 'Nantes', '75102', 'Paris 2e Arrondissement', 30),
    (2018, '95127', 'Cergy', '75101', 'Paris 1er Arrondissement', 20),
    (2018, '75101', 'Paris 1er Arrondissement', '95127', 'Cergy', 40),
    (2020, '75101', 'Paris 1er Arrondissement', '44109', 'Nantes', 150),
    (2020, '44109', 'Nantes', '75101', 'Paris 1er Arrondissement', 20),
    (2020, '75101', 'Paris 1er Arrondissement', '33063', 'Bordeaux', 120),
    (2020, '93066', 'Saint-Denis', '95127', 'Cergy', 60),
    (2020, '97411', 'Saint-Denis', '75101', 'Paris 1er Arrondissement', 10),
    (2020, '95127', 'Cergy', '95127', 'Cergy', 500), #dans la même ville, doit être ignoré
]


@pytest.fixture
def flux():
    df = pd.DataFrame(LIGNES, columns=['annee', 'code_orig', 'nom_orig', 'code_dest', 'nom_dest', 'flux'])
    return preparer_flux(df)


@pytest.fixture
def repertoire(flux):
    return RepertoireCommunes(flux)
