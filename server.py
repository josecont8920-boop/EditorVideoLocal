"""Servidor FastAPI del Editor de Video Local.
100% gratuito, sin APIs de pago. Motor: Coqui TTS + MoviePy + Pillow.
Genera videos en segundo plano para evitar timeouts del proxy en produccion.
"""
import os
import sys
import uuid
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from config import settings

app = FastAPI(title="Editor de Video Local")

# Estado en memoria de los trabajos (simple, sin base de datos).
# Sigue siendo la fuente de verdad para /api/estado/{job_id} tal cual estaba;
# si DATABASE_URL/REDIS_URL estan configuradas, core/orquestador.py ademas
# registra el progreso ahi (ver core/conexiones.py), pero eso no reemplaza
# este dict todavia -- son dos registros en paralelo, no uno dependiente del otro.
TRABAJOS = {}


@app.on_event("startup")
def _startup():
    from core.conexiones import iniciar_conexiones_en_segundo_plano
    iniciar_conexiones_en_segundo_plano()


def _verificar_token_panel(token: Optional[str]):
    """
    Si PANEL_ACCESS_TOKEN esta configurado, lo exige como ?token=... en la
    URL (un navegador no puede mandar headers custom al navegar directo).
    Si no esta configurado, el panel queda abierto -- se avisa en el log.
    """
    if not settings.PANEL_ACCESS_TOKEN:
        return
    if token != settings.PANEL_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Falta ?token=<PANEL_ACCESS_TOKEN> o es incorrecto")


class GenerarVideoRequest(BaseModel):
    texto: str
    titulo: str
    formato: Optional[str] = "vertical"


@app.get("/", response_class=HTMLResponse)
def home():
    return "<h1>Editor de Video Local</h1><p>Motor gratuito de generacion de video: texto -> voz -> video con subtitulos.</p>"


@app.get("/health")
@app.get("/api/health")
def health_check():
    from core.conexiones import ESTADO_CONEXIONES
    return {
        "status": "healthy",
        "service": "EditorVideoLocal",
        "infraestructura": ESTADO_CONEXIONES,
    }


def _procesar_video(job_id: str, texto: str, titulo: str, formato: str):
    TRABAJOS[job_id]["status"] = "processing"
    try:
        from core.orquestador import generar_video
        resultado = generar_video(fuente_texto=texto, titulo=titulo, formato=formato)
        TRABAJOS[job_id]["status"] = "done"
        TRABAJOS[job_id]["resultado"] = resultado
    except Exception as e:
        TRABAJOS[job_id]["status"] = "error"
        TRABAJOS[job_id]["error"] = str(e)


@app.post("/api/generar-video")
def generar_video_endpoint(
    request: GenerarVideoRequest,
    background_tasks: BackgroundTasks,
    token: Optional[str] = Query(default=None),
):
    """Encola la generacion del video y devuelve un job_id de inmediato.
    El video puede tardar varios minutos (TTS + render); consulta el estado
    con GET /api/estado/{job_id}."""
    _verificar_token_panel(token)
    job_id = str(uuid.uuid4())
    TRABAJOS[job_id] = {"status": "queued"}
    background_tasks.add_task(_procesar_video, job_id, request.texto, request.titulo, request.formato)
    return {"status": "queued", "job_id": job_id}


@app.get("/api/estado/{job_id}")
def estado_trabajo(job_id: str):
    if job_id not in TRABAJOS:
        raise HTTPException(status_code=404, detail="job_id no encontrado")
    return TRABAJOS[job_id]


@app.get("/panel", response_class=HTMLResponse)
def panel(token: Optional[str] = Query(default=None)):
    """Panel visual: listado de capitulos, monitor en vivo y formulario de generacion."""
    _verificar_token_panel(token)
    ruta_html = Path(__file__).resolve().parent / "frontend" / "panel.html"
    return HTMLResponse(content=ruta_html.read_text(encoding="utf-8"))


@app.get("/api/estado_sistema")
def estado_sistema(token: Optional[str] = Query(default=None)):
    """
    Todo lo que necesita el panel en una sola llamada: capitulos generados
    (Postgres, o el listado de archivos en output/ si no hay DB conectada),
    trabajos activos (Redis) y el estado de las 3 conexiones de infraestructura.
    """
    _verificar_token_panel(token)
    from core.conexiones import ESTADO_CONEXIONES, listar_capitulos_postgres, listar_trabajos_redis, postgres_disponible

    capitulos = listar_capitulos_postgres()
    if not postgres_disponible():
        # Sin Postgres, se arma un listado basico a partir de los archivos
        # que ya existen en output/, para que el panel nunca quede vacio.
        output_dir = Path(__file__).resolve().parent / "output"
        capitulos = [
            {
                "run_id": p.stem,
                "titulo": p.stem,
                "archivo": p.name,
                "estado": "listo",
                "creado_en": None,
                "num_escenas": None,
                "duracion_total_seg": None,
            }
            for p in sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        ]

    return {
        "capitulos": capitulos,
        "trabajos_activos": listar_trabajos_redis(),
        "infraestructura": ESTADO_CONEXIONES,
    }


@app.post("/api/generar-video-pdf")
def generar_video_pdf_endpoint(
    background_tasks: BackgroundTasks,
    titulo: str = Form(...),
    formato: str = Form("vertical"),
    archivo: UploadFile = File(...),
    token: Optional[str] = Query(default=None),
):
    """Igual que /api/generar-video pero recibiendo un PDF en vez de texto plano."""
    _verificar_token_panel(token)

    if archivo.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(archivo.file.read())
    tmp.close()

    job_id = str(uuid.uuid4())
    TRABAJOS[job_id] = {"status": "queued"}
    background_tasks.add_task(_procesar_video, job_id, tmp.name, titulo, formato)
    return {"status": "queued", "job_id": job_id}


@app.get("/api/descargar/{nombre_archivo}")
def descargar_video(nombre_archivo: str, token: Optional[str] = Query(default=None)):
    _verificar_token_panel(token)
    ruta = Path(__file__).resolve().parent / "output" / nombre_archivo
    if not ruta.exists() or not ruta.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(ruta), media_type="video/mp4", filename=nombre_archivo)
