import streamlit as st

# Configurar la página
st.set_page_config(
    page_title="EstudiApp 📚✨",
    page_icon="📚",
    layout="centered"
)

# Título y banner
st.image("assets/banner_estudiapp.png", use_container_width=True)
st.title("Bienvenidos a EstudiApp 📚✨")

# Inicializar session_state si no existe
if "hija" not in st.session_state:
    st.session_state.hija = None
if "actividad" not in st.session_state:
    st.session_state.actividad = None

# Selección de hija
hija = st.selectbox("¿Quién va a estudiar hoy?", ["Catita", "Leito"])

# Selección de actividad
actividad = st.selectbox(
    "¿Qué quieres hacer?",
    ["Asignaturas Escolares", "Lectura Complementaria"]
)

# Botón para continuar
if st.button("Continuar 🚀"):
    st.session_state.hija = hija
    st.session_state.actividad = actividad
    st.success(f"Perfecto! Vamos a trabajar con {hija} en {actividad}.")
    # Ahora puedes empezar a mostrar el siguiente flujo basado en la selección
