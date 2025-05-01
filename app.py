# kahoot_app.py (actualizado con generación de preguntas vía HuggingFace Space)

import os
import io
import re
import json
import logging
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
import docx
import pandas as pd
import requests
from PIL import Image
from msal import PublicClientApplication, SerializableTokenCache
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

# === CONFIGURACIÓN INICIAL ===
CLIENT_ID = st.secrets["CLIENT_ID"]
AUTHORITY = st.secrets["AUTHORITY"]
SCOPES = [s.strip() for s in st.secrets["SCOPES"].split(",")]
HF_SPACE_URL = "https://ifaundezf-estudiapp-quiz-generator.hf.space/run/predict"

BASE_ONEDRIVE_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/ASIGNATURAS"
BASE_LIBROS_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/LIBROS/MINEDUC"
TOKEN_CACHE_PATH = "token_cache.bin"

@st.cache_resource
def load_ocr_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def ocr_image_huggingface(img):
    try:
        processor, model = load_ocr_model()
        inputs = processor(images=img, return_tensors="pt")
        out = model.generate(**inputs)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        st.warning(f"⚠️ Error OCR en imagen: {e}")
        return ""

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

def download_onedrive_file(file_id, token):
    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response.content if response.status_code == 200 else None

def extract_text_from_docx(doc_bytes):
    text = ""
    doc = docx.Document(io.BytesIO(doc_bytes))
    for para in doc.paragraphs:
        text += para.text + "\n"
    for rel in doc.part._rels:
        rel = doc.part._rels[rel]
        if "image" in rel.target_ref:
            image_data = rel.target_part.blob
            try:
                img = Image.open(io.BytesIO(image_data))
                text += ocr_image_huggingface(img) + "\n"
            except Exception as e:
                st.warning(f"⚠️ Error OCR imagen Word: {e}")
    return text

def extract_text_from_pdf(pdf_bytes):
    text = ""
    try:
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in pdf:
            text += page.get_text()
            for img in page.get_images(full=True):
                try:
                    base_image = pdf.extract_image(img[0])
                    img = Image.open(io.BytesIO(base_image["image"]))
                    text += ocr_image_huggingface(img) + "\n"
                except Exception as e:
                    st.warning(f"⚠️ Error OCR imagen PDF: {e}")
        pdf.close()
    except Exception as e:
        st.error(f"❌ Error leyendo PDF: {e}")
    return text

def extract_unidades(text):
    return sorted(set(re.findall(r"Unidad\s+\d+:.*", text)))

# === INTERFAZ STREAMLIT ===
st.set_page_config(page_title="EstudiApp - OCR y preguntas", layout="centered")
st.title("EstudiApp 📚 - Generación de preguntas con Hugging Face")

hija = st.selectbox("¿Quién va a estudiar?", ["Catita", "Leito"])

if "token" not in st.session_state:
    token = authenticate_onedrive()
    st.session_state.token = token
else:
    token = st.session_state.token

asignatura = st.selectbox("Selecciona asignatura:", ["CIENCIAS", "HISTORIA", "INGLES", "LENGUAJE", "MATEMATICAS"])

# === Carga apuntes ===
base_path = f"{BASE_ONEDRIVE_PATH}/{hija.upper()}/2025"
headers = {"Authorization": f"Bearer {token}"}
archivos = requests.get(f"https://graph.microsoft.com/v1.0/me/drive/root:{base_path}:/children", headers=headers).json()["value"]

docx_file = next((f for f in archivos if f['name'].lower() == f"{asignatura.lower()}.docx"), None)
if not docx_file:
    st.error("❌ Archivo de apuntes no encontrado.")
    st.stop()

st.info("📝 Cargando apuntes...")
doc_bytes = download_onedrive_file(docx_file['id'], token)
texto_apuntes = extract_text_from_docx(doc_bytes)
unidades = extract_unidades(texto_apuntes)

unidad_seleccionada = st.multiselect("Selecciona los temas/unidades (detectadas en apuntes):", unidades)

st.markdown("**📘 ¿Deseas complementar con el libro del MINEDUC?**")
pag_input = st.text_input("Páginas específicas del libro (ej: 1,2,5-10)", key="paginas_pdf")

# === Parámetros ===
tiempo = st.selectbox("Tiempo por pregunta (segundos):", [5,10,20,30,60,90,120])
cantidad = st.slider("¿Cuántas preguntas deseas generar?", 1, 50, 10)

if st.button("Generar preguntas"):
    with st.spinner("🔍 Procesando contenido..."):
        texto_final = texto_apuntes

        libros_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{BASE_LIBROS_PATH}/{hija.upper()}/2025/{asignatura.upper()}:/children"
        response = requests.get(libros_url, headers=headers)
        if response.status_code == 200:
            libros = response.json().get("value", [])
            if libros:
                st.info(f"📚 Se encontraron {len(libros)} libro(s) PDF para complementar.")
                for libro in libros:
                    if libro['name'].lower().endswith(".pdf"):
                        pdf_bytes = download_onedrive_file(libro['id'], token)
                        texto_final += extract_text_from_pdf(pdf_bytes)

        st.success("✨ Contenido listo para generar preguntas")

        try:
            response = requests.post(HF_SPACE_URL, json={"data": [texto_final[:8000], cantidad]})
            if response.status_code == 200:
                preguntas = response.json().get("data", [])
                if preguntas:
                    st.success(f"✅ Se generaron {len(preguntas)} preguntas.")
                    st.json(preguntas)
                    output_path = Path("salidas")
                    output_path.mkdir(exist_ok=True)
                    with open(output_path / f"preguntas_{hija}_{asignatura}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
                        json.dump(preguntas, f, indent=2, ensure_ascii=False)
                else:
                    st.warning("⚠️ HuggingFace respondió sin preguntas válidas.")
            else:
                st.error(f"❌ Error HuggingFace: Código {response.status_code}")
        except Exception as e:
            st.error(f"❌ Falló la conexión con HuggingFace: {e}")
