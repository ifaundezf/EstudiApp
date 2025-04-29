# EstudiApp (Streamlit + HuggingFace OCR)

Esta app permite a estudiantes generar preguntas tipo Kahoot en la nube.

## Flujo:
1. Selecciona hija y asignatura.
2. Se procesan los apuntes (.docx) desde OneDrive.
3. Se procesan libros MINEDUC (.pdf) si están disponibles.
4. Se aplica OCR sobre imágenes usando `microsoft/trocr-base-stage1`.
5. Se generan preguntas usando OpenAI (GPT-4 Turbo).
6. Las preguntas se exportan en formato compatible con Kahoot (.xlsx).

Todo funciona sin requerir instalación local. Ideal para uso móvil.