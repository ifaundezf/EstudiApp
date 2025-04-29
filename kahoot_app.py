# kahoot_app.py

import streamlit as st
import requests
import pandas as pd
import io
import fitz  # PyMuPDF
import docx
import re
import json
import time
from pathlib import Path
from openai import OpenAI

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="EstudiApp", page_icon="📚", layout="centered")
assets_path = Path("./assets")
outputs_path = Path("./outputs")
outputs_path.mkdir(parents=True, exist_ok=True)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# === UTILIDADES ===
def listar_asignaturas(hija):
    # Simulacion de asignaturas para esta demo
    return ["CIENCIAS", "HISTORIA", "LENGUAJE", "MATEMATICAS", "INGLES"]

def extraer_unidades(docx_bytes):
    doc = docx.Document(io.BytesIO(docx_bytes))
    texto = "\n".join([p.text for p in doc.paragraphs])
    unidades = re.findall(r"Unidad\s+\d+:.*", texto)
    return unidades if unidades else ["Todo el contenido"]

def extraer_texto_docx(docx_bytes):
    doc = docx.Document(io.BytesIO(docx_bytes))
    return "\n".join([p.text for p in doc.paragraphs])

def extraer_texto_pdf_paginas(pdf_bytes, paginas):
    texto = ""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i in paginas:
        if i < len(pdf):
            texto += pdf[i].get_text()
    return texto

def generar_preguntas(contenido, cantidad, tiempo, idioma="spanish"):
    prompt = f"""
Genera {cantidad} preguntas tipo Kahoot basadas en el siguiente contenido.
Cada pregunta debe tener 4 alternativas, una sola correcta (numeradas 1 a 4).
Pregunta max 120 caracteres. Alternativa max 75 caracteres.
Tiempo de respuesta: {tiempo} segundos.
Idioma: {idioma}.
Devuelve JSON:
[
 {{"pregunta": "...", "alternativas": ["...", "...", "...", "..."], "correcta": 1}}, ...
]
Contenido:
{contenido[:4000]}
"""
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```json"):
        raw = raw.removeprefix("```json").removesuffix("```")
    return json.loads(raw)

def procesar_rangos_paginas(entrada):
    paginas = []
    partes = entrada.split(",")
    for parte in partes:
        if "-" in parte:
            inicio, fin = map(int, parte.split("-"))
            paginas.extend(range(inicio-1, fin))
        else:
            paginas.append(int(parte)-1)
    return paginas

# === INTERFAZ ===

# ===== Pantalla de Bienvenida =====
if assets_path.joinpath("banner_estudiapp.png").exists():
    st.image(str(assets_path / "banner_estudiapp.png"), use_container_width=True)

st.title("Bienvenidos a EstudiApp 📚✨")
hija = st.selectbox("¿Quién va a estudiar hoy?", ["Catita", "Leito"])
actividad = st.selectbox("¿Qué quieres hacer?", ["Asignaturas Escolares", "Lectura Complementaria"])

if st.button("Continuar 🚀"):
    st.session_state.hija = hija
    st.session_state.actividad = actividad

# ===== Flujo de Asignaturas Escolares =====
if "actividad" in st.session_state and st.session_state.actividad == "Asignaturas Escolares":
    st.header(f"Asignaturas de {st.session_state.hija}")
    asignaturas = listar_asignaturas(st.session_state.hija)
    asignatura = st.selectbox("Selecciona la asignatura:", asignaturas)

    st.subheader("Cargando apuntes...")
    # Simulacion de descarga de Word de apuntes
    docx_bytes = b""  # Aca deberias conectar descarga real

    unidades = extraer_unidades(docx_bytes)
    unidad = st.selectbox("Selecciona la unidad o tema:", unidades)

    st.subheader("¿Deseas usar apoyo de libros MINEDUC?")
    usar_libros = st.radio("Selecciona una opción:", ["No", "Sí"])

    paginas_libro = ""
    if usar_libros == "Sí":
        paginas_libro = st.text_input("Indica páginas específicas o rangos (ej: 1,2,5-10):")

    st.subheader("Configuración del Quiz")
    cantidad = st.number_input("¿Cuántas preguntas quieres generar?", min_value=1, max_value=100, value=10)
    tiempo = st.selectbox("Selecciona tiempo por pregunta:", [5,10,20,30,60,90,120,240])

    if st.button("Generar Preguntas ✨"):
        contenido = extraer_texto_docx(docx_bytes)
        if usar_libros == "Sí" and paginas_libro:
            # Simulacion de descarga de PDF libro
            pdf_bytes = b""  # Aca deberias conectar descarga real
            paginas = procesar_rangos_paginas(paginas_libro)
            contenido += "\n" + extraer_texto_pdf_paginas(pdf_bytes, paginas)

        st.info("Generando preguntas, por favor espera...")
        preguntas = generar_preguntas(contenido, cantidad, tiempo)

        df = pd.DataFrame([{
            "Question": p["pregunta"],
            "Answer 1": p["alternativas"][0],
            "Answer 2": p["alternativas"][1],
            "Answer 3": p["alternativas"][2],
            "Answer 4": p["alternativas"][3],
            "Time limit (sec)": tiempo,
            "Correct answer(s)": p["correcta"]
        } for p in preguntas])

        output_file = outputs_path / f"kahoot_{asignatura}_{int(time.time())}.xlsx"
        df.to_excel(output_file, index=False)

        st.success("¡Preguntas generadas con éxito!")
        st.download_button("Descargar Quiz en Excel", output_file.read_bytes(), file_name=output_file.name)

# (Luego armamos el flujo de Lectura Complementaria como segunda fase)
