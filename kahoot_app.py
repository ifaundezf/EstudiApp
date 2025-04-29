# kahoot_app.py - EstudiApp con OCR Hugging Face (TrOCR) - 100% nube

import os
import io
import re
import json
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
import docx
import requests
import pandas as pd
from PIL import Image
import streamlit as st
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from msal import PublicClientApplication, SerializableTokenCache
from openai import OpenAI

# === CONFIG ===
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
CLIENT_ID = st.secrets["CLIENT_ID"]
AUTHORITY = st.secrets["AUTHORITY"]
SCOPES = [s.strip() for s in st.secrets["SCOPES"].split(",")]

BASE_ONEDRIVE_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/ASIGNATURAS"
BASE_LIBROS_PATH = "/Documents/PERSONAL/PRINCESAS/COLEGIO/LIBROS/MINEDUC"
TOKEN_CACHE_PATH = "token_cache.bin"
TIME_OPTIONS = [5, 10, 20, 30, 60, 90, 120, 240]

now = datetime.now().strftime('%Y%m%d_%H%M%S')

# === OCR Hugging Face TrOCR ===
@st.cache_resource
def load_trocr():
    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-stage1")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-stage1")
    return processor, model

def ocr_image_with_trocr(image):
    processor, model = load_trocr()
    pixel_values = processor(images=image.convert("RGB"), return_tensors="pt").pixel_values
    generated_ids = model.generate(pixel_values)
    return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

# === UTILIDADES ===
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
    r = requests.get(url, headers=headers)
    return r.content if r.status_code == 200 else None

def extract_text_from_docx(doc_bytes):
    text = ""
    doc = docx.Document(io.BytesIO(doc_bytes))
    for p in doc.paragraphs:
        text += p.text + "\n"
    for rel in doc.part._rels.values():
        if "image" in rel.target_ref:
            img_data = rel.target_part.blob
            image = Image.open(io.BytesIO(img_data))
            try:
                text += ocr_image_with_trocr(image) + "\n"
            except Exception as e:
                st.warning(f"❗ Error OCR en imagen Word: {e}")
    return text

def extract_text_from_pdf(pdf_bytes):
    texto = ""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in pdf:
        texto += page.get_text()
        for img in page.get_images(full=True):
            base_img = pdf.extract_image(img[0])
            image_bytes = base_img["image"]
            image = Image.open(io.BytesIO(image_bytes))
            try:
                texto += ocr_image_with_trocr(image) + "\n"
            except Exception as e:
                st.warning(f"❗ Error OCR en imagen PDF: {e}")
    pdf.close()
    return texto

# === APP STREAMLIT ===
def app():
    st.title("EstudiApp 📚 - Versión en la nube con OCR HuggingFace")

    hija = st.selectbox("¿Quién va a estudiar?", ["Catita", "Leito"])
    token = authenticate_onedrive()

    base_path = f"{BASE_ONEDRIVE_PATH}/{hija.upper()}/2025"
    headers = {"Authorization": f"Bearer {token}"}
    archivos = requests.get(f"https://graph.microsoft.com/v1.0/me/drive/root:{base_path}:/children", headers=headers).json()["value"]
    asignaturas = [f['name'].replace('.docx', '') for f in archivos if f['name'].endswith('.docx')]

    asignatura = st.selectbox("Selecciona asignatura:", asignaturas)
    if asignatura:
        docx_id = next(f['id'] for f in archivos if f['name'] == f"{asignatura}.docx")
        st.write("📄 Procesando apuntes...")
        docx_bytes = download_onedrive_file(docx_id, token)
        texto_docx = extract_text_from_docx(docx_bytes)

        libro_url = f"{BASE_LIBROS_PATH}/{hija.upper()}/2025/{asignatura.upper()}"
        libro_api_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{libro_url}:/children"
        libros = requests.get(libro_api_url, headers=headers).json().get("value", [])
        texto_libros = ""
        for libro in libros:
            if libro["name"].endswith(".pdf"):
                st.write(f"📘 Leyendo libro: {libro['name']}")
                libro_bytes = download_onedrive_file(libro['id'], token)
                texto_libros += extract_text_from_pdf(libro_bytes)

        contenido = texto_docx + "\n" + texto_libros
        cantidad = st.number_input("¿Cuántas preguntas quieres?", min_value=1, max_value=100, value=10)
        tiempo = st.selectbox("Tiempo por pregunta (seg):", TIME_OPTIONS)

        if st.button("Generar preguntas"):
            from openai import OpenAI
            prompt = f"""
Genera {cantidad} preguntas tipo Kahoot del siguiente contenido:
- 4 alternativas por pregunta
- solo una es correcta
- pregunta máx 120 caracteres
- alternativa máx 75 caracteres
Devuelve un JSON como:
[{{"pregunta": "...", "alternativas": ["...", "...", "...", "..."], "correcta": 1}}]
Contenido:
{contenido[:4000]}
"""
            with st.spinner("Consultando OpenAI..."):
                r = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                raw = r.choices[0].message.content.strip()
                if raw.startswith("```json"):
                    raw = raw.removeprefix("```json").removesuffix("```").strip()
                preguntas = json.loads(raw)

            df = pd.DataFrame([{
                "Question": p["pregunta"],
                "Answer 1": p["alternativas"][0],
                "Answer 2": p["alternativas"][1],
                "Answer 3": p["alternativas"][2],
                "Answer 4": p["alternativas"][3],
                "Time limit (sec)": tiempo,
                "Correct answer(s)": p["correcta"]
            } for p in preguntas])

            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            st.download_button("📥 Descargar preguntas Excel Kahoot", data=buffer.getvalue(), file_name="preguntas_kahoot.xlsx")

if __name__ == "__main__":
    app()