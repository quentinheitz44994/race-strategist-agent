from app.agent.state import AgentState
from app.agent.writer import run_writer
from app.core.athlete import AthleteProfile


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, content: str):
        self._content = content
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> FakeLLMResponse:
        self.last_prompt = prompt
        return FakeLLMResponse(self._content)


def test_writer_injecte_les_vraies_valeurs_du_profil_dans_le_prompt():
    athlete = AthleteProfile(
        name="test", weight_kg=70, reference_distance_m=42_195, flat_pace_s_per_km=285.3,
        predicted_time_s=12_030, riegel_exponent=1.084, riegel_coefficient=0.1,
        endurance_rating="dans la norme", warnings=["Extrapolation à 1.7x"], source="config/athlete.json",
    )
    state: AgentState = {"athlete": athlete}
    fake_llm = FakeLLM("# Rapport\n...")

    result = run_writer(state, llm=fake_llm)

    assert "1.084" in fake_llm.last_prompt
    assert "Extrapolation à 1.7x" in fake_llm.last_prompt
    assert result["report_md"] == "# Rapport\n..."


def test_writer_signale_les_donnees_manquantes_sans_planter():
    state: AgentState = {}
    fake_llm = FakeLLM("# Rapport minimal")

    result = run_writer(state, llm=fake_llm)

    assert "non disponible" in fake_llm.last_prompt
    assert result["report_md"] == "# Rapport minimal"
