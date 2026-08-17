"""Síntesis de voz 100% local con Coqui TTS. No requiere API key ni internet
tras la primera descarga del modelo."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import TTS_MODEL, OUTPUT_DIR

_tts_instance = None


def _obtener_tts():
    """Carga el modelo una sola vez (es pesado) y lo reutiliza."""
    global _tts_instance
    if _tts_instance is None:
        from TTS.api import TTS
        _tts_instance = TTS(model_name=TTS_MODEL, progress_bar=False)
    return _tts_instance


def sintetizar_escena(texto: str, run_id: str, orden: int) -> dict:
    """Genera el audio de una escena y devuelve la ruta + duración."""
    tts = _obtener_tts()
    carpeta_run = OUTPUT_DIR / run_id / "audio"
    carpeta_run.mkdir(parents=True, exist_ok=True)
    ruta_audio = carpeta_run / f"escena_{orden:02d}.wav"

    tts.tts_to_file(text=texto, file_path=str(ruta_audio))

    duracion = _obtener_duracion(ruta_audio)
    return {"ruta": str(ruta_audio), "duracion_seg": duracion}


def _obtener_duracion(ruta_audio: Path) -> float:
    import wave
    with wave.open(str(ruta_audio), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return round(frames / float(rate), 2)
