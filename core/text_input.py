"""Recibe texto plano o PDF y lo normaliza a un solo string de trabajo."""
from pathlib import Path
from pypdf import PdfReader


def cargar_texto(fuente: str) -> str:
    """fuente puede ser: texto directo, ruta a .txt, o ruta a .pdf"""
    path = Path(fuente)

    if path.exists() and path.suffix.lower() == ".pdf":
        return _extraer_pdf(path)

    if path.exists() and path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8")

    # Si no es una ruta válida, se asume que ya es el texto en crudo
    return fuente.strip()


def _extraer_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    partes = []
    for pagina in reader.pages:
        texto = pagina.extract_text() or ""
        partes.append(texto.strip())
    return "\n\n".join(p for p in partes if p)
