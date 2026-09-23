import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Race Strategist", layout="wide")
st.title("Race Strategist Agent")

with st.form("plan_form"):
    gpx_file = st.file_uploader("Trace GPX de la course", type=["gpx"])
    race_date = st.date_input("Date de la course")
    target_time_h = st.number_input(
        "Temps cible (heures, optionnel)", min_value=0.0, value=0.0, step=0.5
    )
    submitted = st.form_submit_button("Générer le plan")

if submitted:
    if gpx_file is None:
        st.error("Merci d'uploader un fichier GPX.")
    else:
        with st.spinner(
            "L'agent travaille : parcours, profil, météo, calibrage, allure, nutrition. "
            "Les calculs prennent 1 à 2 s ; l'essentiel de l'attente vient des appels au LLM, "
            "mis en file d'attente sur le palier gratuit (jusqu'à plusieurs minutes)."
        ):
            files = {"gpx": (gpx_file.name, gpx_file.getvalue(), "application/gpx+xml")}
            data = {"race_date": race_date.isoformat()}
            if target_time_h > 0:
                data["target_time_s"] = target_time_h * 3600

            try:
                # Large : 4 appels LLM peuvent chacun attendre >2 min sur le palier gratuit.
                response = requests.post(f"{API_URL}/plan", files=files, data=data, timeout=900)
                response.raise_for_status()
            except requests.RequestException as error:
                st.error(f"L'agent n'a pas pu répondre : {error}")
            else:
                result = response.json()
                st.session_state["plan_result"] = result

if "plan_result" in st.session_state:
    result = st.session_state["plan_result"]

    st.markdown(result["report_md"])

    st.subheader("Journal des appels d'outils")
    for call in result["tool_calls"]:
        icon = "✅" if call["success"] else "❌"
        label = f"{icon} `{call['tool_name']}`"
        if call["error"]:
            label += f" — {call['error']}"
        st.markdown(f"- {label}")
