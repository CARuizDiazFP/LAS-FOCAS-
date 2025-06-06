from docx import Document
from .gpt_handler import gpt

async def procesar_incidencias_docx(ruta: str) -> str:
    """Extrae texto de un archivo .docx y lo envía a GPT."""
    doc = Document(ruta)
    texto = "\n".join(p.text for p in doc.paragraphs if p.text)
    return await gpt.consultar_gpt(texto)
