"""
core/conexiones.py
Gestion modular de infraestructura: Postgres, MongoDB y Redis.

Diseno clave: NINGUNA de las 3 conexiones bloquea el arranque del servidor.
`iniciar_conexiones_en_segundo_plano()` lanza un hilo daemon que intenta
conectar cada servicio con reintentos y backoff exponencial; mientras tanto
(o si finalmente falla), el resto de la app sigue funcionando con esa pieza
desactivada -- exactamente igual que hoy sin ninguna de las 3 configuradas.

Cada conexion se expone por separado y siempre a traves de sus funciones
`obtener_*()`, nunca importando el cliente crudo directo, para que quien
las use no tenga que preocuparse por si ya estan listas o no.
"""

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger("editorvideolocal.conexiones")
logging.basicConfig(level=logging.INFO)

# Estado observable (por ejemplo desde un endpoint /health mas detallado)
ESTADO_CONEXIONES = {
    "postgres": {"habilitada": settings.POSTGRES_ENABLED, "conectada": False, "ultimo_error": None},
    "mongo": {"habilitada": settings.MONGO_ENABLED, "conectada": False, "ultimo_error": None},
    "redis": {"habilitada": settings.REDIS_ENABLED, "conectada": False, "ultimo_error": None},
}

# Clientes cacheados (se crean una sola vez, se reutilizan)
_postgres_pool = None
_mongo_client = None
_mongo_db = None
_redis_client = None

_lock = threading.Lock()


# ==========================================================================
# Reintentos con backoff exponencial (generico, reutilizado por los 3)
# ==========================================================================

def _reintentar(nombre_servicio: str, intento_conexion, max_reintentos=None, backoff_base=None):
    """
    Ejecuta `intento_conexion()` (funcion sin argumentos que conecta y
    devuelve el cliente, o lanza excepcion si falla). Reintenta con backoff
    exponencial hasta `max_reintentos` veces. Nunca lanza: si se agotan los
    intentos, registra el error en ESTADO_CONEXIONES y devuelve None.
    """
    max_reintentos = max_reintentos or settings.CONEXION_MAX_REINTENTOS
    backoff_base = backoff_base or settings.CONEXION_BACKOFF_BASE_SEG

    for intento in range(1, max_reintentos + 1):
        try:
            cliente = intento_conexion()
            ESTADO_CONEXIONES[nombre_servicio]["conectada"] = True
            ESTADO_CONEXIONES[nombre_servicio]["ultimo_error"] = None
            logger.info("[%s] Conectado (intento %s/%s).", nombre_servicio, intento, max_reintentos)
            return cliente
        except Exception as e:
            espera = backoff_base * (2 ** (intento - 1))
            logger.warning(
                "[%s] Fallo intento %s/%s: %s. Reintentando en %.1fs...",
                nombre_servicio, intento, max_reintentos, e, espera,
            )
            ESTADO_CONEXIONES[nombre_servicio]["ultimo_error"] = str(e)
            if intento < max_reintentos:
                time.sleep(espera)

    logger.error(
        "[%s] No se pudo conectar tras %s intentos. Se desactiva esta pieza; "
        "el resto de la app sigue funcionando sin ella.",
        nombre_servicio, max_reintentos,
    )
    ESTADO_CONEXIONES[nombre_servicio]["conectada"] = False
    return None


# ==========================================================================
# Postgres: registro persistente de minicapitulos generados
# ==========================================================================

_TABLA_SQL = """
CREATE TABLE IF NOT EXISTS capitulos (
    id SERIAL PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    formato TEXT,
    estado TEXT NOT NULL DEFAULT 'generando',
    archivo TEXT,
    num_escenas INTEGER,
    duracion_total_seg NUMERIC,
    error_mensaje TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _conectar_postgres():
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(_TABLA_SQL)
    conn.commit()
    return conn


def _inicializar_postgres():
    global _postgres_pool
    if not settings.POSTGRES_ENABLED:
        logger.info("[postgres] DATABASE_URL no configurada; registro persistente desactivado.")
        return
    with _lock:
        _postgres_pool = _reintentar("postgres", _conectar_postgres)


@contextmanager
def _conexion_postgres():
    """
    Da una conexion nueva por operacion (mas simple y robusto que compartir
    una sola conexion entre requests concurrentes de FastAPI). Si Postgres
    no esta disponible, no entra al bloque `with` -- el llamador ya debe
    haber chequeado `postgres_disponible()` antes.
    """
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def postgres_disponible() -> bool:
    return settings.POSTGRES_ENABLED and ESTADO_CONEXIONES["postgres"]["conectada"]


def registrar_capitulo_generando(run_id: str, titulo: str, formato: str) -> None:
    if not postgres_disponible():
        return
    try:
        with _conexion_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO capitulos (run_id, titulo, formato, estado)
                       VALUES (%s, %s, %s, 'generando')
                       ON CONFLICT (run_id) DO NOTHING""",
                    (run_id, titulo, formato),
                )
    except Exception as e:
        logger.warning("[postgres] No se pudo registrar 'generando' para run_id=%s: %s", run_id, e)


def registrar_capitulo_listo(run_id: str, archivo: str, num_escenas: int, duracion_total_seg: float) -> None:
    if not postgres_disponible():
        return
    try:
        with _conexion_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE capitulos SET estado='listo', archivo=%s, num_escenas=%s,
                       duracion_total_seg=%s, actualizado_en=%s WHERE run_id=%s""",
                    (archivo, num_escenas, duracion_total_seg, datetime.now(timezone.utc), run_id),
                )
    except Exception as e:
        logger.warning("[postgres] No se pudo registrar 'listo' para run_id=%s: %s", run_id, e)


def registrar_capitulo_error(run_id: str, mensaje: str) -> None:
    if not postgres_disponible():
        return
    try:
        with _conexion_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE capitulos SET estado='error', error_mensaje=%s,
                       actualizado_en=%s WHERE run_id=%s""",
                    (mensaje[:2000], datetime.now(timezone.utc), run_id),
                )
    except Exception as e:
        logger.warning("[postgres] No se pudo registrar 'error' para run_id=%s: %s", run_id, e)


def _serializar_fila(fila: dict) -> dict:
    """Convierte tipos no serializables a JSON (datetime, Decimal) a str/float."""
    from decimal import Decimal
    limpio = {}
    for k, v in fila.items():
        if isinstance(v, datetime):
            limpio[k] = v.isoformat()
        elif isinstance(v, Decimal):
            limpio[k] = float(v)
        else:
            limpio[k] = v
    return limpio


def listar_capitulos_postgres(limite: int = 50) -> list:
    """Para el panel: capitulos ya generados (o en error), mas recientes primero."""
    if not postgres_disponible():
        return []
    try:
        import psycopg2.extras
        with _conexion_postgres() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM capitulos ORDER BY creado_en DESC LIMIT %s", (limite,))
                return [_serializar_fila(dict(f)) for f in cur.fetchall()]
    except Exception as e:
        logger.warning("[postgres] No se pudo listar capitulos: %s", e)
        return []


# ==========================================================================
# MongoDB: metadatos flexibles del guion y las escenas por capitulo
# ==========================================================================

def _conectar_mongo():
    from pymongo import MongoClient
    cliente = MongoClient(settings.MONGO_URL, serverSelectionTimeoutMS=5000)
    cliente.admin.command("ping")  # fuerza la conexion real, no solo el objeto
    return cliente


def _inicializar_mongo():
    global _mongo_client, _mongo_db
    if not settings.MONGO_ENABLED:
        logger.info("[mongo] MONGO_URL no configurada; metadatos extendidos desactivados.")
        return
    with _lock:
        _mongo_client = _reintentar("mongo", _conectar_mongo)
        if _mongo_client is not None:
            _mongo_db = _mongo_client[settings.MONGO_DB_NAME]


def mongo_disponible() -> bool:
    return settings.MONGO_ENABLED and ESTADO_CONEXIONES["mongo"]["conectada"] and _mongo_db is not None


def guardar_guion_mongo(run_id: str, titulo: str, escenas: list) -> None:
    """Guarda el guion completo (texto, emocion, duracion por escena) como
    documento flexible, sin necesidad de migrar esquema si cambian los campos."""
    if not mongo_disponible():
        return
    try:
        _mongo_db.guiones.update_one(
            {"run_id": run_id},
            {"$set": {
                "run_id": run_id,
                "titulo": titulo,
                "escenas": escenas,
                "actualizado_en": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("[mongo] No se pudo guardar el guion de run_id=%s: %s", run_id, e)


# ==========================================================================
# Redis: cola de renderizado + cache de estado de trabajos
# ==========================================================================

def _conectar_redis():
    import redis
    cliente = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=5)
    cliente.ping()  # fuerza la conexion real
    return cliente


def _inicializar_redis():
    global _redis_client
    if not settings.REDIS_ENABLED:
        logger.info("[redis] REDIS_URL no configurada; cola de renderizado desactivada (se usa BackgroundTasks en memoria).")
        return
    with _lock:
        _redis_client = _reintentar("redis", _conectar_redis)


def redis_disponible() -> bool:
    return settings.REDIS_ENABLED and ESTADO_CONEXIONES["redis"]["conectada"] and _redis_client is not None


def encolar_tarea_renderizado(run_id: str, payload: dict) -> bool:
    """
    Empuja un trabajo de renderizado a la cola de Redis (lista), para que un
    worker separado pueda procesarlo (base para escalar mas alla de
    BackgroundTasks en un solo proceso). Devuelve True si se encolo.
    Si Redis no esta disponible, el llamador debe seguir con el flujo actual
    (procesar en el mismo proceso via BackgroundTasks) sin fallar.
    """
    if not redis_disponible():
        return False
    try:
        tarea = {"run_id": run_id, "encolado_en": datetime.now(timezone.utc).isoformat(), **payload}
        _redis_client.rpush(settings.REDIS_COLA_RENDERIZADO, json.dumps(tarea))
        _redis_client.hset(f"trabajo:{run_id}", mapping={"status": "queued"})
        return True
    except Exception as e:
        logger.warning("[redis] No se pudo encolar run_id=%s: %s", run_id, e)
        return False


def actualizar_estado_trabajo_redis(run_id: str, status: str, **extra) -> None:
    if not redis_disponible():
        return
    try:
        _redis_client.hset(f"trabajo:{run_id}", mapping={"status": status, **{k: str(v) for k, v in extra.items()}})
        # Los trabajos terminados o con error expiran solos tras 1h para no
        # acumular basura en Redis; los "en progreso" no tienen TTL.
        if status in ("listo", "error"):
            _redis_client.expire(f"trabajo:{run_id}", 3600)
    except Exception as e:
        logger.warning("[redis] No se pudo actualizar estado de run_id=%s: %s", run_id, e)


def listar_trabajos_redis(limite: int = 50) -> list:
    """
    Para el panel: snapshot de trabajos con actividad reciente en Redis
    (incluye los que estan 'generando' ahora mismo, ademas de los recien
    terminados que todavia no expiraron). Usa SCAN en vez de KEYS para no
    bloquear Redis aunque haya muchas claves.
    """
    if not redis_disponible():
        return []
    try:
        trabajos = []
        for clave in _redis_client.scan_iter(match="trabajo:*", count=100):
            datos = _redis_client.hgetall(clave)
            if not datos:
                continue
            run_id = clave.decode() if isinstance(clave, bytes) else clave
            run_id = run_id.split("trabajo:", 1)[-1]
            fila = {k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v for k, v in datos.items()}
            fila["run_id"] = run_id
            trabajos.append(fila)
            if len(trabajos) >= limite:
                break
        return trabajos
    except Exception as e:
        logger.warning("[redis] No se pudo listar trabajos activos: %s", e)
        return []


# ==========================================================================
# Arranque no bloqueante
# ==========================================================================

def iniciar_conexiones_en_segundo_plano() -> None:
    """
    Llamar UNA VEZ al arrancar el servidor (evento startup de FastAPI).
    Lanza un hilo daemon que intenta las 3 conexiones con reintentos; el
    servidor sigue arrancando y sirviendo /health de inmediato sin esperar
    a que terminen (ni aunque nunca se conecten).
    """
    def _worker():
        _inicializar_postgres()
        _inicializar_mongo()
        _inicializar_redis()
        logger.info("Estado final de conexiones: %s", ESTADO_CONEXIONES)

    hilo = threading.Thread(target=_worker, name="conexiones-infra", daemon=True)
    hilo.start()
