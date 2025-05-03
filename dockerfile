# Imagen base con Python
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos al contenedor
COPY . .

# Instala las dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expone el puerto que usará Streamlit (lo que Azure espera es 80, pero redirigiremos)
EXPOSE 8501

RUN mkdir -p /root/.streamlit
COPY .streamlit/secrets.toml /root/.streamlit/secrets.toml

# Comando para ejecutar Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
