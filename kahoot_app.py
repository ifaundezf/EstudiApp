# kahoot_app.py (Versión final completa con apuntes + libros MINEDUC y exportación Kahoot)

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
from msal import PublicClientApplication, SerializableTokenCache
from openai import OpenAI
import streamlit as st

# === CONFIGURACIÓN INICIAL ===
os.environ["TESSDATA_PREFIX"] = "/opt/homebrew/share/tessdata/"
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
CLIENT_ID = st.secrets["CLIENT_ID"]
AUTHORITY = st.secrets["AUTHORITY"]
SCOPES = [s.strip() for s in st.secrets["SCOPES"].split(",")]

BASE_ONEDRIVE_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/ASIGNATURAS"
BASE_LIBROS_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/LIBROS/MINEDUC"
BASE_OUTPUT_PATH = Path("./salidas")
TOKEN_CACHE_PATH = "token_cache.bin"
TIME_OPTIONS = [5, 10, 20, 30, 60, 90, 120, 240]

client = OpenAI(api_key=OPENAI_API_KEY)
now = datetime.now().strftime('%Y%m%d_%H%M%S')

# === FUNCIONES ===
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
    st.info(f"🔐 Ve a {flow['verification_uri']} e ingresa el código: {flow['user_code']}")
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        with open(TOKEN_CACHE_PATH, "w") as f:
            f.write(cache.serialize())
        return result['access_token']
    else:
        raise Exception("Error autenticando con Microsoft Graph")

# ... (resto del código sin cambios)


def download_onedrive_file(file_id, token):
    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response.content if response.status_code == 200 else None

def extract_unidades(text):
    return sorted(set(re.findall(r"Unidad\s+\d+:.*", text)))

def extract_text_from_docx(doc_bytes):
    doc = docx.Document(io.BytesIO(doc_bytes))
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(pdf_bytes, paginas=None):
    texto = ""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i, pagina in enumerate(pdf):
        if paginas is None or i + 1 in paginas:
            texto += pagina.get_text()
            for img in pagina.get_images(full=True):
                base_image = pdf.extract_image(img[0])
                image_bytes = base_image["image"]
                img = Image.open(io.BytesIO(image_bytes)).convert("L")
                img = img.filter(ImageFilter.MedianFilter())
                img = ImageEnhance.Contrast(img).enhance(2.0)
                texto += pytesseract.image_to_string(img, lang="spa") + "\n"
    pdf.close()
    return texto

def parsear_paginas(paginas_str):
    if not paginas_str:
        return None
    paginas = set()
    for parte in paginas_str.split(','):
        if '-' in parte:
            ini, fin = map(int, parte.split('-'))
            paginas.update(range(ini, fin+1))
        else:
            paginas.add(int(parte))
    return paginas

def generar_prompt(contenido, cantidad, asignatura, tiempo):
    idioma = "english" if asignatura.strip().lower() == "ingles" else "spanish"
    instruccion = "Write the questions in English." if idioma == "english" else "Redacta las preguntas en español."
    return f"""
Genera {cantidad} preguntas tipo Kahoot a partir del siguiente contenido.
Cada pregunta debe tener 4 alternativas, una sola correcta, y cumplir:
- Máximo 120 caracteres para la pregunta
- Máximo 75 caracteres por alternativa
- El tiempo para responder será de {tiempo} segundos.
{instruccion}

Devuelve un JSON con esta estructura:
[
  {{"pregunta": "...", "alternativas": ["...", "...", "...", "..."], "correcta": 1}}, ...
]
La respuesta correcta debe ser SIEMPRE un número entre 1 y 4.
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
        return [p for p in preguntas if isinstance(p, dict) and "pregunta" in p and "alternativas" in p and 1 <= p.get("correcta", 0) <= 4]
    except Exception as e:
        st.error(f"❌ Error generando preguntas: {e}")
        return []

def app():
    st.title("Bienvenidos a EstudiApp 📚✨")
    hija = st.selectbox("¿Quién va a estudiar hoy?", ["Catita", "Leito"])
    actividad = st.selectbox("¿Qué quieres hacer?", ["Asignaturas Escolares"])

    if st.button("Continuar 🚀"):
        st.session_state.hija = hija
        st.session_state.actividad = actividad
        st.rerun()

    if st.session_state.get("actividad") == "Asignaturas Escolares":
        token = authenticate_onedrive()

        st.header(f"Asignaturas de {st.session_state.hija}")
        base_path = f"{BASE_ONEDRIVE_PATH}/{st.session_state.hija.upper()}/2025"
        headers = {"Authorization": f"Bearer {token}"}
        archivos = requests.get(f"https://graph.microsoft.com/v1.0/me/drive/root:{base_path}:/children", headers=headers).json()["value"]
        asignaturas = [f['name'].replace('.docx', '') for f in archivos if f['name'].endswith('.docx')]

        asignatura = st.selectbox("Selecciona asignatura:", asignaturas)
        if asignatura:
            docx_id = next(f['id'] for f in archivos if f['name'] == f"{asignatura}.docx")
            docx_bytes = download_onedrive_file(docx_id, token)
            texto_docx = extract_text_from_docx(docx_bytes)

            unidades = extract_unidades(texto_docx)
            temas = st.multiselect("Selecciona los temas/unidades: (extraídos del apunte)", unidades)

            st.subheader("📘 Páginas opcionales del libro MINEDUC:")
            paginas_input = st.text_input("Ejemplo: 1,2,5-10")
            paginas = parsear_paginas(paginas_input)

            # Buscar libro
            libro_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{BASE_LIBROS_PATH}/{st.session_state.hija.upper()}/2025/{asignatura.upper()}:/children"
            libros = requests.get(libro_url, headers=headers).json().get("value", [])
            texto_libro = ""
            for libro in libros:
                if libro['name'].endswith(".pdf"):
                    libro_bytes = download_onedrive_file(libro['id'], token)
                    texto_libro += extract_text_from_pdf(libro_bytes, paginas)

            contenido_filtrado = "\n".join([line for line in texto_docx.split("\n") if any(t in line for t in temas)]) if temas else texto_docx
            contenido_completo = contenido_filtrado + "\n" + texto_libro

            cantidad = st.number_input("¿Cuántas preguntas quieres generar?", min_value=1, max_value=100, value=10)
            tiempo = st.selectbox("Selecciona el tiempo límite por pregunta:", TIME_OPTIONS)

            if st.button("Generar Preguntas 🎯"):
                with st.spinner("Generando preguntas con OpenAI..."):
                    preguntas = generar_preguntas(contenido_completo, cantidad, asignatura, tiempo)

                if preguntas:
                    st.success(f"✅ Se generaron {len(preguntas)} preguntas")
                    st.write("Vista previa de las 3 primeras preguntas:")
                    for p in preguntas[:3]:
                        st.markdown(f"**{p['pregunta']}**\n- 1: {p['alternativas'][0]}\n- 2: {p['alternativas'][1]}\n- 3: {p['alternativas'][2]}\n- 4: {p['alternativas'][3]}")

                    df = pd.DataFrame([{
                        "Question": p["pregunta"],
                        "Answer 1": p["alternativas"][0],
                        "Answer 2": p["alternativas"][1],
                        "Answer 3": p["alternativas"][2],
                        "Answer 4": p["alternativas"][3],
                        "Time limit (sec)": tiempo,
                        "Correct answer(s)": p["correcta"]
                    } for p in preguntas])

                    excel_bytes = io.BytesIO()
                    with pd.ExcelWriter(excel_bytes, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button("📥 Descargar Excel compatible con Kahoot", data=excel_bytes.getvalue(), file_name="preguntas_kahoot.xlsx")
                else:
                    st.error("No se pudieron generar preguntas. Revisa el contenido o intenta con otro tema.")

if __name__ == "__main__":
    app()
