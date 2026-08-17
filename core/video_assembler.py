"""Ensamblaje del video final: imagenes + audio + subtitulos + musica.
100% local con MoviePy y FFmpeg, sin dependencias de pago."""
from pathlib import Path
import sys
import random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    OUTPUT_DIR, RESOLUCIONES, FORMATO_DEFAULT,
    SUBTITULO_FONT, SUBTITULO_TAMANO, SUBTITULO_COLOR,
    ASSETS_MUSIC,
)

# Parche de compatibilidad: Pillow >=10 elimino Image.ANTIALIAS,
# que MoviePy 1.0.3 todavia usa internamente.
from PIL import Image as _PILImage
if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.LANCZOS

from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, CompositeAudioClip,
    afx,
)


def ensamblar_video(escenas: list[dict], run_id: str, titulo: str,
                     formato: str = None) -> Path:
    formato = formato or FORMATO_DEFAULT
    ancho, alto = RESOLUCIONES[formato]

    clips = []
    for escena in escenas:
        clip = _construir_clip_escena(escena, ancho, alto)
        clips.append(clip)

    video_final = concatenate_videoclips(clips, method="compose", padding=-0.3)
    video_final = _agregar_musica_fondo(video_final)

    salida = OUTPUT_DIR / f"{_slug(titulo)}_{run_id}.mp4"
    video_final.write_videofile(
        str(salida), fps=30, codec="libx264", audio_codec="aac",
        threads=4, preset="medium",
        bitrate="5000k", audio_bitrate="192k",
    )
    return salida


def _construir_clip_escena(escena: dict, ancho: int, alto: int):
    audio = AudioFileClip(escena["audio_ruta"])
    duracion = audio.duration

    imagen = ImageClip(escena["imagen_ruta"]).set_duration(duracion)
    imagen = imagen.resize(height=alto)
    if imagen.w < ancho:
        imagen = imagen.resize(width=ancho)

    imagen = _aplicar_ken_burns(imagen, duracion, ancho, alto)
    imagen = imagen.set_audio(audio)

    subtitulo = _crear_subtitulo(escena["texto"], duracion, ancho, alto)

    clip_final = CompositeVideoClip([imagen, subtitulo], size=(ancho, alto))
    # CompositeVideoClip NO hereda el audio automaticamente, hay que asignarlo.
    clip_final = clip_final.set_audio(audio)
    return clip_final


def _aplicar_ken_burns(clip, duracion, ancho, alto):
    zoom_inicial = 1.0
    zoom_final = random.uniform(1.08, 1.18)
    if random.random() > 0.5:
        zoom_inicial, zoom_final = zoom_final, zoom_inicial

    def efecto_zoom(t):
        progreso = t / duracion if duracion > 0 else 0
        return zoom_inicial + (zoom_final - zoom_inicial) * progreso

    return clip.resize(efecto_zoom).set_position("center")


def _crear_subtitulo(texto: str, duracion: float, ancho: int, alto: int):
    # Renderiza el subtitulo con Pillow en vez de ImageMagick/TextClip.
    # Mas robusto: funciona igual en cualquier servidor, sin depender de
    # convert/policy.xml que varian entre entornos (local vs Railway).
    import numpy as np
    from PIL import Image as PILImage, ImageDraw, ImageFont

    ancho_texto = int(ancho * 0.85)
    try:
        fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", SUBTITULO_TAMANO)
    except Exception:
        fuente = ImageFont.load_default()

    palabras = texto.split()
    lineas, linea_actual = [], ""
    tmp_img = PILImage.new("RGBA", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp_img)
    for palabra in palabras:
        candidato = (linea_actual + " " + palabra).strip()
        bbox = tmp_draw.textbbox((0, 0), candidato, font=fuente)
        if bbox[2] - bbox[0] > ancho_texto and linea_actual:
            lineas.append(linea_actual)
            linea_actual = palabra
        else:
            linea_actual = candidato
    if linea_actual:
        lineas.append(linea_actual)

    alto_linea = SUBTITULO_TAMANO + 14
    alto_total = alto_linea * len(lineas) + 20
    img = PILImage.new("RGBA", (ancho, alto_total), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, linea in enumerate(lineas):
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        w = bbox[2] - bbox[0]
        x = (ancho - w) / 2
        y = 10 + i * alto_linea
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx or dy:
                    draw.text((x + dx, y + dy), linea, font=fuente, fill=(0, 0, 0, 255))
        draw.text((x, y), linea, font=fuente, fill=(255, 255, 255, 255))

    frame = np.array(img)
    txt_clip = ImageClip(frame, transparent=True)
    txt_clip = txt_clip.set_duration(duracion)
    txt_clip = txt_clip.set_position(("center", int(alto * 0.78)))
    return txt_clip.fadein(0.2).fadeout(0.2)


def _agregar_musica_fondo(video):
    pistas = list(ASSETS_MUSIC.glob("*.mp3")) + list(ASSETS_MUSIC.glob("*.wav"))
    if not pistas:
        return video

    pista = random.choice(pistas)
    musica = AudioFileClip(str(pista)).fx(afx.audio_loop, duration=video.duration)
    musica = musica.fx(afx.volumex, 0.15).fx(afx.audio_fadein, 1).fx(afx.audio_fadeout, 1)

    audio_final = CompositeAudioClip([video.audio, musica])
    return video.set_audio(audio_final)


def _slug(texto: str) -> str:
    import re
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "_", texto)
    return texto[:50]
