import pytest

from app.core.fueling import MAX_FLUID_ML_PER_H, compute_fueling_plan


def test_course_courte_demande_peu_de_glucides():
    plan = compute_fueling_plan(duration_h=0.8, temp_c=10.0)
    assert plan.carbs_g_per_h.high <= 30.0


def test_course_longue_monte_vers_le_haut_de_la_fourchette():
    courte = compute_fueling_plan(duration_h=2.0, temp_c=10.0)
    longue = compute_fueling_plan(duration_h=8.0, temp_c=10.0)
    assert longue.carbs_g_per_h.low > courte.carbs_g_per_h.low
    assert any("2 h 30" in note for note in longue.notes)


def test_la_chaleur_augmente_l_hydratation():
    tempere = compute_fueling_plan(duration_h=5.0, temp_c=10.0)
    chaud = compute_fueling_plan(duration_h=5.0, temp_c=28.0)
    assert chaud.fluid_ml_per_h.low > tempere.fluid_ml_per_h.low
    assert any("Hydratation majorée" in note for note in chaud.notes)


def test_l_hydratation_est_plafonnee():
    plan = compute_fueling_plan(duration_h=5.0, temp_c=40.0)
    assert plan.fluid_ml_per_h.high <= MAX_FLUID_ML_PER_H
    assert any("plafonné" in note for note in plan.notes)


def test_le_sodium_suit_le_volume_de_liquide():
    tempere = compute_fueling_plan(duration_h=5.0, temp_c=10.0)
    chaud = compute_fueling_plan(duration_h=5.0, temp_c=28.0)
    assert chaud.sodium_mg_per_h.low > tempere.sodium_mg_per_h.low


def test_l_intensite_module_les_apports():
    faible = compute_fueling_plan(duration_h=5.0, temp_c=10.0, intensity="faible")
    eleve = compute_fueling_plan(duration_h=5.0, temp_c=10.0, intensity="élevé")
    assert eleve.carbs_g_per_h.high > faible.carbs_g_per_h.high


def test_les_totaux_sont_coherents_avec_la_duree():
    plan = compute_fueling_plan(duration_h=6.0, temp_c=12.0)
    assert plan.total_carbs_g.low == pytest.approx(plan.carbs_g_per_h.low * 6.0)
    assert plan.total_fluid_ml.high == pytest.approx(plan.fluid_ml_per_h.high * 6.0)


def test_l_avertissement_est_toujours_present():
    plan = compute_fueling_plan(duration_h=3.0, temp_c=15.0)
    assert "à tester à l'entraînement" in plan.disclaimer


def test_duree_nulle_ou_negative_leve_une_erreur():
    with pytest.raises(ValueError):
        compute_fueling_plan(duration_h=0.0, temp_c=15.0)
