"""Orquesta el pipeline completo: texto -> escenas -> audio -> video final."""
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.text_input import cargar_texto
from core.scene_processor import dividir_en_escenas
from core.tts_engine import sintetizar_escena
from core.video_assembler import ensamblar_video
from core.asset_selector import elegir_imagen_por_emocion
from core import conexiones


def generar_video(fuente_texto: str, titulo: str, formato: str = None) -> dict:
    """
    Punto de entrada unico. fuente_texto puede ser texto plano, .txt o .pdf.

    Si hay Postgres/Mongo/Redis configurados (ver config/settings.py y
    core/conexiones.py), este flujo registra el progreso del minicapitulo
    en cada uno. Ninguno es obligatorio: si alguno no esta disponible (o
    directamente no esta configurado), el video se genera igual -- las
    llamadas a `conexiones.*` nunca lanzan excepciones hacia aqui.
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    formato_final = formato or "vertical"

    conexiones.registrar_capitulo_generando(run_id, titulo, formato_final)
    conexiones.actualizar_estado_trabajo_redis(run_id, "generando")
    # Si mas adelante quieren mover el renderizado a un worker separado,
    # aqui es donde se encolaria en vez de seguir el flujo sincrono:
    #   conexiones.encolar_tarea_renderizado(run_id, {"titulo": titulo, "formato": formato_final})

    try:
        texto = cargar_texto(fuente_texto)
        if not texto.strip():
            raise ValueError("El texto de entrada esta vacio")

        escenas_base = dividir_en_escenas(texto)
        if not escenas_base:
            raise ValueError("No se pudo dividir el texto en escenas")

        escenas_completas = []
        for escena in escenas_base:
            audio_info = sintetizar_escena(escena["texto"], run_id, escena["orden"])
            imagen_ruta = elegir_imagen_por_emocion(escena["emocion"])

            escenas_completas.append({
                "orden": escena["orden"],
                "texto": escena["texto"],
                "emocion": escena["emocion"],
                "audio_ruta": audio_info["ruta"],
                "duracion_seg": audio_info["duracion_seg"],
                "imagen_ruta": imagen_ruta,
            })

        # Metadatos flexibles (texto completo, emociones detectadas por
        # escena) -- encajan mejor en Mongo que en columnas fijas de Postgres.
        conexiones.guardar_guion_mongo(run_id, titulo, escenas_completas)

        # Libera la memoria del modelo TTS (PyTorch) antes de renderizar el
        # video. Reduce el pico de RAM, critico en servidores con poca memoria.
        import gc
        from core import tts_engine
        tts_engine._tts_instance = None
        gc.collect()

        ruta_video = ensamblar_video(escenas_completas, run_id, titulo, formato)

        resultado = {
            "run_id": run_id,
            "titulo": titulo,
            "archivo": ruta_video.name,
            "ruta_completa": str(ruta_video),
            "num_escenas": len(escenas_completas),
            "duracion_total_seg": round(sum(e["duracion_seg"] for e in escenas_completas), 2),
        }

        conexiones.registrar_capitulo_listo(
            run_id, resultado["archivo"], resultado["num_escenas"], resultado["duracion_total_seg"]
        )
        conexiones.actualizar_estado_trabajo_redis(run_id, "listo", archivo=resultado["archivo"])

        return resultado

    except Exception as e:
        conexiones.registrar_capitulo_error(run_id, str(e))
        conexiones.actualizar_estado_trabajo_redis(run_id, "error", error=str(e))
        raise
