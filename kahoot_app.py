# kahoot_app.py

import streamlit as st
from pathlib import Path

# === CONFIGURACIÓN DE PÁGINA ===
st.set_page_config(
    page_title="EstudiApp - Generador de Quizzes",
    page_icon="📚",
    layout="centered",
)

# === CARGAR IMAGEN DE BIENVENIDA ===
assets_path = Path("./assets")
banner_path = assets_path / "banner_estudiapp.png"

if banner_path.exists():
    st.image(str(banner_path))
else:
    st.write("📚 Bienvenido a **EstudiApp**")

st.title("Bienvenidos a EstudiApp 📚✨")
st.markdown("Selecciona a quién quieres ayudar hoy:")

# === SELECCIÓN DE HIJA ===
hija = st.selectbox(
    "¿Quién va a estudiar hoy?",
    ("Catita", "Leito")
)

# === SELECCIÓN DE ACTIVIDAD ===
actividad = st.selectbox(
    "¿Qué quieres hacer?",
    ("Asignaturas Escolares", "Lectura Complementaria")
)

# === BOTÓN CONTINUAR ===
if st.button("Continuar 🚀"):
    if actividad == "Asignaturas Escolares":
        st.session_state["hija"] = hija
        st.session_state["modo"] = "asignaturas"
        st.experimental_rerun()
    elif actividad == "Lectura Complementaria":
        st.session_state["hija"] = hija
        st.session_state["modo"] = "lectura"
        st.experimental_rerun()

# === FLUJO DE ACTIVIDADES ===
if "modo" in st.session_state:
    if st.session_state["modo"] == "asignaturas":
        st.header(f"📖 Generar Quiz para {st.session_state['hija']} - Asignaturas")
        st.write("🔜 Aquí cargaremos el flujo de apuntes + libros MINEDUC...")
    elif st.session_state["modo"] == "lectura":
        st.header(f"📖 Generar Quiz para {st.session_state['hija']} - Lectura Complementaria")
        st.write("🔜 Aquí cargaremos el flujo de libros de lectura subida por ustedes...")
