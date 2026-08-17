import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_BACKGROUNDS = BASE_DIR / "assets" / "backgrounds"
ASSETS_MUSIC = BASE_DIR / "assets" / "music"
OUTPUT_DIR = BASE_DIR / "output"
DATA_PENDIENTES = BASE_DIR / "data" / "textos_pendientes"
DATA_PROCESADOS = BASE_DIR / "data" / "textos_procesados"

# TTS local (Coqui) - modelo español multi-voz, 100% offline tras la primera descarga
TTS_MODEL = os.getenv("TTS_MODEL", "tts_models/es/css10/vits")

# Formato de video por defecto
FORMATO_DEFAULT = os.getenv("FORMATO_VIDEO", "vertical")  # vertical | horizontal
RESOLUCIONES = {
    "vertical": (1080, 1920),
    "horizontal": (1920, 1080),
}

# Subtítulos
SUBTITULO_FONT = os.getenv("SUBTITULO_FONT", "DejaVu-Sans-Bold")
SUBTITULO_TAMANO = int(os.getenv("SUBTITULO_TAMANO", "60"))
SUBTITULO_COLOR = os.getenv("SUBTITULO_COLOR", "white")

for d in [ASSETS_BACKGROUNDS, ASSETS_MUSIC, OUTPUT_DIR, DATA_PENDIENTES, DATA_PROCESADOS]:
    d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Infraestructura (Railway inyecta estas variables automaticamente cuando
# conectas un plugin de Postgres/Mongo/Redis al servicio, normalmente como
# referencia: DATABASE_URL=${{Postgres.DATABASE_URL}}, etc.)
#
# Ninguna de las 3 es obligatoria: el editor funciona 100% local/offline sin
# ellas (como hasta ahora). Si estan presentes, habilitan persistencia de
# trabajos, metadatos de guiones y cola de renderizado respectivamente.
# --------------------------------------------------------------------------

# Postgres: estado/registro de cada minicapitulo generado (reemplaza el
# diccionario en memoria TRABAJOS de server.py, que se pierde en cada redeploy)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# MongoDB: metadatos dinamicos por capitulo (guion completo, escenas,
# emociones detectadas) - esquema flexible, no requiere migraciones.
# Railway/Atlas pueden exponerla como MONGO_URL o MONGODB_URI segun el plugin.
MONGO_URL = os.getenv("MONGO_URL", os.getenv("MONGODB_URI", ""))
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "editorvideolocal")

# Redis: cola de tareas asincronas de renderizado (para escalar mas alla de
# BackgroundTasks en memoria) y cache de estado de trabajos.
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_COLA_RENDERIZADO = os.getenv("REDIS_COLA_RENDERIZADO", "cola:renderizado")

# Flags derivados: el resto del codigo debe consultar estos antes de usar
# cada conexion, nunca asumir que estan disponibles.
POSTGRES_ENABLED = bool(DATABASE_URL)
MONGO_ENABLED = bool(MONGO_URL)
REDIS_ENABLED = bool(REDIS_URL)

# Reintentos de conexion (no bloqueantes: corren en un hilo de fondo al
# arrancar el servidor, ver core/conexiones.py)
CONEXION_MAX_REINTENTOS = int(os.getenv("CONEXION_MAX_REINTENTOS", "5"))
CONEXION_BACKOFF_BASE_SEG = float(os.getenv("CONEXION_BACKOFF_BASE_SEG", "2"))

# Panel web (/panel): si se configura, se exige como ?token=<valor> en la URL
# para ver/descargar los capitulos. Si se deja vacio, el panel queda abierto
# a cualquiera que tenga la URL de Railway -- recomendado configurarlo.
PANEL_ACCESS_TOKEN = os.getenv("PANEL_ACCESS_TOKEN", "")
