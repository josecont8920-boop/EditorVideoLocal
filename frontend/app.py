"""Front-end ligero en Streamlit para el motor local de generación de video.

Ejecutar desde la raíz del repo:
    streamlit run local_engine/frontend/app.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from core.orquestador import generar_video
from config.settings import RESOLUCIONES

st.set_page_config(page_title="Motor Local de Video", page_icon="🎬", layout="centered")

st.title("🎬 Motor Local de Generación de Video")
st.caption("100% local · sin APIs de pago · Coqui TTS + MoviePy")

with st.form("form_generar"):
    titulo = st.text_input("Título del video", placeholder="Ej: Los colores primarios")

    modo_entrada = st.radio("Fuente del texto", ["Escribir texto", "Subir PDF"], horizontal=True)

    texto_directo = ""
    archivo_pdf = None

    if modo_entrada == "Escribir texto":
        texto_directo = st.text_area(
            "Texto / guion", height=220,
            placeholder="Pega aquí el guion, artículo o fragmento a convertir en video...",
        )
    else:
        archivo_pdf = st.file_uploader("Sube un PDF", type=["pdf"])

    col1, col2 = st.columns(2)
    with col1:
        formato = st.selectbox("Formato", options=list(RESOLUCIONES.keys()), index=0)
    with col2:
        st.write("")
        st.write("")
        st.caption(f"Resolución: {RESOLUCIONES[formato][0]}x{RESOLUCIONES[formato][1]}")

    enviado = st.form_submit_button("Generar video 🚀", use_container_width=True)

if enviado:
    if not titulo.strip():
        st.error("Ingresa un título para el video.")
    elif modo_entrada == "Escribir texto" and not texto_directo.strip():
        st.error("Ingresa el texto o guion.")
    elif modo_entrada == "Subir PDF" and archivo_pdf is None:
        st.error("Sube un archivo PDF.")
    else:
        fuente = texto_directo
        if modo_entrada == "Subir PDF":
            temp_path = Path("/tmp") / archivo_pdf.name
            temp_path.write_bytes(archivo_pdf.getvalue())
            fuente = str(temp_path)

        with st.spinner("Generando video... esto puede tardar varios minutos (TTS + render)."):
            try:
                resultado = generar_video(fuente, titulo, formato)
                st.success(f"¡Video generado! {resultado['num_escenas']} escenas, "
                           f"{resultado['duracion_total_seg']}s de duración.")
                video_path = Path(resultado["ruta_completa"])
                if video_path.exists():
                    st.video(str(video_path))
                    with open(video_path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar video", f, file_name=resultado["archivo"],
                            mime="video/mp4", use_container_width=True,
                        )
            except Exception as e:
                st.error(f"Error al generar el video: {e}")

st.divider()
st.caption(
    "Coloca imágenes de fondo en local_engine/assets/backgrounds/ "
    "(opcionalmente en subcarpetas por emoción: feliz/, pensativo/, sorprendido/, hablando/) "
    "y música opcional en local_engine/assets/music/."
)
