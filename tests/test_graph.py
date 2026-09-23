from app.agent.graph import build_graph


def test_le_graphe_se_compile_sans_erreur():
    graph = build_graph()
    assert graph is not None
