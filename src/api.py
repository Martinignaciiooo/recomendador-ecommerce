"""
API REST del sistema de recomendación.

Implementa las decisiones arquitectónicas documentadas en el informe:
  - AD1: estrategia híbrida (caché LRU + inferencia en tiempo real)
  - AD3: fallback a productos más vendidos ante cold start o fallo del modelo
  - AD4: carga el modelo activo desde un registro versionado (puntero 'current')
  - Observabilidad: latencia p50/p95/p99, tasas de caché, fallback y error
  - Seguridad: autenticación Bearer (si RECO_API_TOKEN está definido); HTTPS lo
    termina el proxy inverso (Caddy) delante del servicio

Ejecutar:  uvicorn api:app --host 0.0.0.0 --port 8000
"""
import datetime as dt
import hmac
import uuid
import json
import logging
import threading
import os
import sqlite3
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import Recommender, default_model_root, resolve_current
from cloud_ep2 import download_model, send_event

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

LATENCY_BUDGET_MS = float(os.environ.get("LATENCY_BUDGET_MS", "150"))
CACHE_MAX = int(os.environ.get("CACHE_MAX", "20000"))
API_TOKEN = os.environ.get("RECO_API_TOKEN", "")  # vacío = sin autenticación (solo desarrollo)


# ----------------------------------------------------------------------
# Estado del servicio
# ----------------------------------------------------------------------
class State:
    def __init__(self):
        self.rec: Optional[Recommender] = None
        self.events_db = ""
        self.cache: "OrderedDict[tuple, list]" = OrderedDict()
        self.latencies = deque(maxlen=5000)
        self.counts = {"total": 0, "model": 0, "cache": 0, "fallback": 0, "error": 0, "eventos": 0}
        self.started = dt.datetime.now().isoformat(timespec="seconds")


state = State()
cache_lock = threading.RLock()
log = logging.getLogger("shopfast")
logging.basicConfig(level=logging.INFO)


def init_events_db(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS eventos ("
            " event_time TEXT NOT NULL, event_type TEXT NOT NULL,"
            " product_id INTEGER NOT NULL, user_id INTEGER NOT NULL)"
        )


def load_state():
    if len(API_TOKEN) < 32 and os.environ.get("RECO_ALLOW_ANONYMOUS") != "1":
        raise RuntimeError("RECO_API_TOKEN de al menos 32 caracteres es obligatorio")
    download_model()
    state.rec = Recommender(resolve_current(default_model_root()))
    state.events_db = os.environ.get("EVENTS_DB", os.path.join(BASE, "out", "eventos.db"))
    if os.environ.get("EVENTS_BACKEND", "sqlite") == "sqlite":
        init_events_db(state.events_db)
    state.cache.clear()


@asynccontextmanager
async def lifespan(app):
    load_state()
    yield


app = FastAPI(
    title="API de Recomendación de Productos",
    description="Sistema de recomendación para e-commerce — Caso 1, ITY1102",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if os.environ.get("PRODUCTION") == "1" else "/docs",
    redoc_url=None if os.environ.get("PRODUCTION") == "1" else "/redoc",
)


def verificar_token(authorization: Optional[str] = Header(None)):
    if not API_TOKEN and os.environ.get("RECO_ALLOW_ANONYMOUS") == "1":
        return
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if len(API_TOKEN) < 32 or not hmac.compare_digest(supplied.encode(), API_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Token inválido o ausente")


# ----------------------------------------------------------------------
# Esquemas
# ----------------------------------------------------------------------
class Producto(BaseModel):
    product_id: int
    score: float
    categoria: Optional[str] = None
    marca: Optional[str] = None
    precio: Optional[float] = None


class RespuestaRecomendacion(BaseModel):
    # user_id como texto: los IDs del dataset superan el entero seguro de JavaScript
    user_id: str
    recommendations: List[Producto]
    source: Literal["model", "cache", "fallback"]
    latency_ms: float
    model_version: str


class Evento(BaseModel):
    user_id: int
    product_id: int
    event_type: Literal["view", "cart", "purchase"]


# ----------------------------------------------------------------------
# Lógica
# ----------------------------------------------------------------------
def _cache_get(key):
    val = state.cache.get(key)
    if val is not None:
        state.cache.move_to_end(key)
    return val


def _cache_put(key, val):
    state.cache[key] = val
    state.cache.move_to_end(key)
    while len(state.cache) > CACHE_MAX:
        state.cache.popitem(last=False)


def _cache_invalidate_user(user_id):
    for key in [k for k in state.cache if k[0] == user_id]:
        del state.cache[key]


def cache_get(key):
    with cache_lock: return _cache_get(key)

def cache_put(key, val):
    with cache_lock: return _cache_put(key,val)

def cache_invalidate_user(user_id):
    with cache_lock: return _cache_invalidate_user(user_id)

@app.middleware("http")
async def request_log(request: Request, call_next):
    rid=str(uuid.uuid4());start=time.perf_counter()
    response=await call_next(request)
    response.headers["X-Request-ID"]=rid
    log.info(json.dumps({"request_id":rid,"status":response.status_code,"latency_ms":round((time.perf_counter()-start)*1000,3)}))
    return response


def enrich(pairs):
    out = []
    for pid, score in pairs:
        d = state.rec.describe(pid)
        out.append(Producto(product_id=pid, score=round(score, 5), categoria=d.get("categoria"),
                            marca=d.get("marca"), precio=d.get("precio")))
    return out


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/recomendaciones", response_model=RespuestaRecomendacion, dependencies=[Depends(verificar_token)])
def recomendaciones(user_id: int, k: int = 10):
    if k < 1 or k > 50:
        raise HTTPException(status_code=400, detail="k debe estar entre 1 y 50")

    t0 = time.perf_counter()
    state.counts["total"] += 1
    try:
        cached = cache_get((user_id, k))
        if cached is not None:
            pairs, source = cached, "cache"
        else:
            pairs = state.rec.personalized(user_id, k)
            elapsed = (time.perf_counter() - t0) * 1000
            if pairs is None or elapsed > LATENCY_BUDGET_MS:
                pairs, source = state.rec.fallback(k), "fallback"
            else:
                source = "model"
                cache_put((user_id, k), pairs)
    except Exception:
        state.counts["error"] += 1
        pairs, source = state.rec.fallback(k), "fallback"

    state.counts[source] += 1
    latency = (time.perf_counter() - t0) * 1000
    state.latencies.append(latency)
    return RespuestaRecomendacion(user_id=str(user_id), recommendations=enrich(pairs), source=source,
                                  latency_ms=round(latency, 3), model_version=state.rec.version)


@app.post("/eventos", status_code=202, dependencies=[Depends(verificar_token)])
def registrar_evento(ev: Evento, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    """Acepta evento duradero. Reintentos deben reutilizar el mismo UUID."""
    try:
        event_id=str(uuid.UUID(idempotency_key))
    except ValueError:
        raise HTTPException(422, "Idempotency-Key debe ser UUID")
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    if os.environ.get("EVENTS_BACKEND", "sqlite") == "sqs":
        try:
            send_event({"event_id":event_id,"user_id":str(ev.user_id),"product_id":str(ev.product_id),
                        "interaction_type":ev.event_type,"timestamp":ts})
        except Exception:
            log.error(json.dumps({"event":"queue_unavailable"}))
            raise HTTPException(503, "No aceptado; reintente con el mismo Idempotency-Key")
    else:
        # Compatibilidad local. Idempotencia también en SQLite para pruebas.
        with sqlite3.connect(state.events_db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS event_keys (event_id TEXT PRIMARY KEY)")
            cursor=con.execute("INSERT OR IGNORE INTO event_keys VALUES (?)",(event_id,))
            if cursor.rowcount:
                con.execute("INSERT INTO eventos VALUES (?, ?, ?, ?)", (ts, ev.event_type, ev.product_id, ev.user_id))
    cache_invalidate_user(ev.user_id)
    state.counts["eventos"] += 1
    return {"aceptado":True,"event_id":event_id,"event_time":ts,"cache_invalidada_para":str(ev.user_id)}


@app.get("/salud")
def salud():
    """Health check para el balanceador y el pipeline de despliegue."""
    if state.rec is None:
        raise HTTPException(503,"Modelo no listo")
    return {"estado": "ok",
            "modelo": state.rec.version if state.rec else None}


@app.get("/metricas", dependencies=[Depends(verificar_token)])
def metricas():
    lat = np.array(state.latencies) if state.latencies else np.array([0.0])
    n = max(state.counts["total"], 1)
    return {
        "solicitudes_totales": state.counts["total"],
        "eventos_registrados": state.counts["eventos"],
        "latencia_ms": {p: round(float(np.percentile(lat, q)), 3) for p, q in (("p50", 50), ("p95", 95), ("p99", 99))},
        "tasa_modelo": round(state.counts["model"] / n, 4),
        "tasa_cache_hit": round(state.counts["cache"] / n, 4),
        "tasa_fallback": round(state.counts["fallback"] / n, 4),
        "tasa_error": round(state.counts["error"] / n, 4),
        "entradas_cache": len(state.cache),
        "presupuesto_latencia_ms": LATENCY_BUDGET_MS,
        "modelo": state.rec.version,
        "activo_desde": state.started,
    }


@app.get("/modelo", dependencies=[Depends(verificar_token)])
def modelo():
    """Metadatos del modelo activo: versión, configuración y métricas offline."""
    m = state.rec.meta
    return {k: m[k] for k in ("version", "entrenado_en", "algoritmo", "config", "corte_temporal",
                              "dimensiones", "metricas_offline", "baseline_popularidad", "usuarios_test")}


@app.get("/usuarios-ejemplo", dependencies=[Depends(verificar_token)])
def usuarios_ejemplo(n: int = 5):
    """IDs de usuarios conocidos por el modelo (como texto), para la demo."""
    ids = list(state.rec.uidx.keys())
    step = max(len(ids) // max(n, 1), 1)
    return [str(u) for u in ids[::step][:n]]


@app.get("/dashboard", include_in_schema=False)
@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(os.path.join(HERE, "static", "dashboard.html"))

@app.get("/health/ready")
def readiness(): return salud()

@app.get("/health/live")
def liveness(): return {"estado":"up"}
