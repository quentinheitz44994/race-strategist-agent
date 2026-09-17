import pytest

from app.agent.tools import TOOLS, get_tool


def test_tous_les_outils_ont_un_nom_et_une_description():
    for tool in TOOLS:
        assert tool.name
        assert tool.description
        assert callable(tool.func)


def test_les_noms_d_outils_sont_uniques():
    noms = [tool.name for tool in TOOLS]
    assert len(noms) == len(set(noms))


def test_get_tool_retrouve_un_outil_existant():
    tool = get_tool("segment_route")
    assert tool.name == "segment_route"


def test_get_tool_leve_une_erreur_sur_un_nom_inconnu():
    with pytest.raises(KeyError):
        get_tool("outil_qui_n_existe_pas")
