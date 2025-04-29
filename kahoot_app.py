# kahoot_app.py (Versión unificada para EstudiApp)

import os
import io
import re
import json
import logging
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
import docx
import pytesseract
import pandas as pd
import requests
from PIL import Image, ImageEnhance, ImageFilter
from dotenv import load_dotenv
from msal import PublicClientApplication, SerializableTokenCache
from openai import OpenAI
import streamlit as st

# Configuración Inicial
os.environ["TESSDATA_PREFIX"] = "/opt/homebrew/share/tessdata/"
load_dotenv()

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
CLIENT_ID = st.secrets["CLIENT_ID"]

AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Files.Read.All"]

BASE_ONEDRIVE_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/ASIGNATURAS"
BASE_LIBROS_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/LIBROS/MINEDUC"
BASE_OUTPUT_PATH = Path("./salidas")
TOKEN_CACHE_PATH = "token_cache.bin"
TIME_OPTIONS = [5, 10, 20, 30, 60, 90, 120, 240]

client = OpenAI(api_key=OPENAI_API_KEY)

now = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = f'kahoot_generator_{now}.log'
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# === FUNCIONES UTILITARIAS ===

def authenticate_onedrive():
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        cache.deserialize(open(TOKEN_CACHE_PATH, "r").read())
    app = PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result:
            return result['access_token']

    flow = app.initiate_device_flow(scopes=SCOPES)
    st.info(f"🔒 Autenticación requerida. Visita {flow['verification_uri']} e ingresa el código: {flow['user_code']}")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        with open(TOKEN_CACHE_PATH, "w") as f:
            f.write(cache.serialize())
        return result['access_token']
    else:
        raise Exception("Error autenticando con Microsoft Graph")

def download_onedrive_file(file_id, token):
    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response.content if response.status_code == 200 else None

def extract_unidades(texto):
    unidades = sorted(set(re.findall(r"Unidad\s+\d+:.*", texto)))
    return unidades

def extract_text_from_docx(docx_bytes):
    doc = docx.Document(io.BytesIO(docx_bytes))
    text = "\n".join([p.text for p in doc.paragraphs])
    return text

def generar_prompt(contenido, cantidad, asignatura, tiempo):
    idioma = "english" if asignatura.strip().lower() == "ingles" else "spanish"
    instruccion_idioma = "Write the questions in English." if idioma == "english" else "Redacta las preguntas en español."
    return f"""
Genera {cantidad} preguntas tipo Kahoot a partir del siguiente contenido.\nCada pregunta debe tener 4 alternativas, una sola correcta, y cumplir:\n- Máximo 120 caracteres para la pregunta\n- Máximo 75 caracteres por alternativa\n- El tiempo para responder cada pregunta será de {tiempo} segundos.\n{instruccion_idioma}\n\nDevuelve un JSON con esta estructura exacta:\n[\n  {{\"pregunta\": \"...\", \"alternativas\": [\"...\", \"...\", \"...\", \"...\"], \"correcta\": 1}}, ...\n]\n\nLa respuesta correcta debe ser SIEMPRE un número entre 1 y 4.
Contenido:
{contenido[:4000]}
"""

def generar_preguntas(contenido, cantidad, asignatura, tiempo):
    prompt = generar_prompt(contenido, cantidad, asignatura, tiempo)
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```json"):
            raw = raw.removeprefix("```json").removesuffix("```").strip()
        preguntas = json.loads(raw)
        return preguntas
    except Exception as e:
        st.error(f"Error generando preguntas: {e}")
        logging.error(f"Error generando preguntas: {e}")
        return []

def exportar_preguntas_excel(preguntas, tiempo):
    df = pd.DataFrame([{
        "Question": p["pregunta"],
        "Answer 1": p["alternativas"][0],
        "Answer 2": p["alternativas"][1],
        "Answer 3": p["alternativas"][2],
        "Answer 4": p["alternativas"][3],
        "Time limit (sec)": tiempo,
        "Correct answer(s)": p["correcta"]
    } for p in preguntas])
    return df


# === FLUJO PRINCIPAL DE STREAMLIT ===

def app():
    st.title("Bienvenidos a EstudiApp 📚✨")
    hija = st.selectbox("¿Quién va a estudiar hoy?", ["Catita", "Leito"])
    actividad = st.selectbox("¿Qué quieres hacer?", ["Asignaturas Escolares"])

    if st.button("Continuar 🚀"):
        st.session_state.hija = hija
        st.session_state.actividad = actividad
        st.experimental_rerun()

    if "actividad" in st.session_state and st.session_state.actividad == "Asignaturas Escolares":
        st.header(f"Asignaturas de {st.session_state.hija}")

        token = authenticate_onedrive()

        base_path = f"{BASE_ONEDRIVE_PATH}/{st.session_state.hija.upper()}/2025"
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:{base_path}:/children"
        headers = {"Authorization": f"Bearer {token}"}
        archivos = requests.get(url, headers=headers).json()["value"]
        asignaturas = [f['name'].replace('.docx', '') for f in archivos if f['name'].endswith('.docx')]

        asignatura = st.selectbox("Selecciona la asignatura:", asignaturas)

        if asignatura:
            st.subheader("Cargando apuntes...")
            try:
                docx_id = next(f['id'] for f in archivos if f['name'] == f"{asignatura}.docx")
                docx_bytes = download_onedrive_file(docx_id, token)
                texto_docx = extract_text_from_docx(docx_bytes)

                unidades = extract_unidades(texto_docx)
                if unidades:
                    tema_seleccionado = st.multiselect("Selecciona los temas/unidades:", unidades)
                else:
                    st.warning("No se detectaron unidades. Se usará todo el contenido.")

                st.subheader("Opcional: Seleccionar páginas de libros MINEDUC")
                paginas = st.text_input("Ingresa páginas o rangos separados por coma (ej: 1,2,5-10)")

                cantidad = st.number_input("¿Cuántas preguntas deseas generar?", min_value=1, max_value=100, value=10)
                tiempo = st.selectbox("Selecciona el tiempo límite por pregunta (segundos):", TIME_OPTIONS)

                if st.button("Generar Preguntas 🎯"):
                    with st.spinner("Generando preguntas con OpenAI..."):

                        contenido_final = texto_docx
                        if tema_seleccionado:
                            contenido_final = "\n".join([p for p in texto_docx.split("\n") if any(t in p for t in tema_seleccionado)])

                        preguntas = generar_preguntas(contenido_final, cantidad, asignatura, tiempo)

                        if preguntas:
                            df = exportar_preguntas_excel(preguntas, tiempo)
                            st.success("✅ ¡Preguntas generadas exitosamente!")
                            st.download_button(
                                label="Descargar preguntas en formato Kahoot 📥",
                                data=df.to_excel(index=False, engine='openpyxl'),
                                file_name=f"preguntas_{asignatura}_{now}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.error("❌ No se pudieron generar preguntas. Revisa los registros.")

            except Exception as e:
                st.error(f"Error cargando apuntes: {e}")

if __name__ == "__main__":
    app()
