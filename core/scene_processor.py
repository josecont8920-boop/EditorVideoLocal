"""Divide un texto largo en escenas/bloques usando reglas estructuradas.
No depende de ninguna API externa: usa puntuación, longitud y párrafos.
"""
import re

MAX_PALABRAS_POR_ESCENA = 40


def dividir_en_escenas(texto: str) -> list[dict]:
    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    escenas = []
    orden = 1

    for parrafo in parrafos:
        oraciones = re.split(r'(?<=[.!?])\s+', parrafo)
        bloque_actual = ""

        for oracion in oraciones:
            candidato = (bloque_actual + " " + oracion).strip()
            if len(candidato.split()) > MAX_PALABRAS_POR_ESCENA and bloque_actual:
                escenas.append(_nueva_escena(orden, bloque_actual))
                orden += 1
                bloque_actual = oracion
            else:
                bloque_actual = candidato

        if bloque_actual:
            escenas.append(_nueva_escena(orden, bloque_actual))
            orden += 1

    return escenas


def _nueva_escena(orden: int, texto: str) -> dict:
    return {
        "orden": orden,
        "texto": texto.strip(),
        "emocion": _inferir_emocion(texto),
    }


def _inferir_emocion(texto: str) -> str:
    """Heurística simple por palabras clave. Se puede sustituir
    por un clasificador local (ej. modelo de sentimiento offline)."""
    t = texto.lower()
    if any(w in t for w in ["!", "increíble", "wow", "sorprend"]):
        return "sorprendido"
    if any(w in t for w in ["feliz", "alegr", "genial", "bien"]):
        return "feliz"
    if any(w in t for w in ["piensa", "quizás", "tal vez", "hmm"]):
        return "pensativo"
    return "hablando"
