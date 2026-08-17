"""Recibe texto plano o PDF y lo normaliza a un solo string de trabajo."""
from pathlib import Path
from pypdf import PdfReader


def cargar_texto(fuente: str) -> str:
    """fuente puede ser: texto directo, ruta a .txt, o ruta a .pdf"""
    if _parece_ruta_de_archivo(fuente):
        path = Path(fuente)
        if path.exists() and path.suffix.lower() == ".pdf":
            return _extraer_pdf(path)
        if path.exists() and path.suffix.lower() == ".txt":
            return path.read_text(encoding="utf-8")

    # Si no es una ruta valida, se asume que ya es el texto en crudo
    return fuente.strip()


def _parece_ruta_de_archivo(fuente: str) -> bool:
    """
    Antes de tocar el sistema de archivos, descarta lo que claramente es
    texto largo (el guion en si, con saltos de linea o mas de ~200
    caracteres). Sin este filtro, Path(fuente).exists() intenta resolver
    un "nombre de archivo" del largo del guion completo y el sistema
    operativo lo rechaza con OSError: [Errno 36] File name too long.
    """
    if not fuente or "\n" in fuente:
        return False
    if len(fuente) > 200:
        return False
    return True


def _extraer_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    partes = []
    for pagina in reader.pages:
        texto = pagina.extract_text() or ""
        partes.append(texto.strip())
    return "\n\n".join(p for p in partes if p)
