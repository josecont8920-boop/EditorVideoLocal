"""Elige una imagen/fondo de assets/backgrounds/ según la emoción de la escena.

Convención de carpetas (opcional pero recomendada):
    assets/backgrounds/feliz/*.jpg
    assets/backgrounds/pensativo/*.jpg
    assets/backgrounds/sorprendido/*.jpg
    assets/backgrounds/hablando/*.jpg

Si no existen subcarpetas por emoción, se usa cualquier imagen suelta
directamente dentro de assets/backgrounds/ como fallback genérico.
"""
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ASSETS_BACKGROUNDS

EXTENSIONES_VALIDAS = ("*.jpg", "*.jpeg", "*.png", "*.webp")


def elegir_imagen_por_emocion(emocion: str) -> str:
    carpeta_emocion = ASSETS_BACKGROUNDS / emocion
    imagenes = _listar_imagenes(carpeta_emocion) if carpeta_emocion.exists() else []

    if not imagenes:
        imagenes = _listar_imagenes(ASSETS_BACKGROUNDS)

    if not imagenes:
        raise FileNotFoundError(
            f"No hay imagenes en {ASSETS_BACKGROUNDS}. "
            "Agrega al menos una imagen (.jpg/.png) para poder generar el video."
        )

    return str(random.choice(imagenes))


def _listar_imagenes(carpeta: Path) -> list[Path]:
    resultado = []
    for patron in EXTENSIONES_VALIDAS:
        resultado.extend(carpeta.glob(patron))
    return resultado
