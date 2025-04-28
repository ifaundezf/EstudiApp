
# EstudiApp 📚✨

**EstudiApp** es una aplicación construida en Python y Streamlit que permite a Catita y Leito generar quizzes tipo Kahoot para sus asignaturas escolares y lecturas complementarias.

## Funcionalidades
- Selección de hija (`Catita` o `Leito`).
- Creación de quizzes desde:
  - Asignaturas escolares (apuntes + libros MINEDUC).
  - Libros de lectura complementaria.
- Procesamiento automático de Word, PDFs, imágenes OCR.
- Generación de preguntas con OpenAI.
- Exportación en formato Excel listo para Kahoot.

## Estructura del proyecto
```
EstudiApp/
├── assets/
│    └── banner_estudiapp.png
├── outputs/
│    └── .gitkeep
├── utils/
│    └── .gitkeep
├── kahoot_app.py
├── requirements.txt
└── README.md
```

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu_usuario/EstudiApp.git
cd EstudiApp

# Crear entorno virtual (opcional pero recomendado)
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la app
streamlit run kahoot_app.py
```

## Variables de entorno requeridas (.env)
- `OPENAI_API_KEY`
- `CLIENT_ID`
- `TESSDATA_PREFIX`

## Autor
Creado con 💙 para Catita y Leito por [Tu Nombre Aquí].
