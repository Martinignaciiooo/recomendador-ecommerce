"""
Tests del sistema de recomendación.

  - unitarios   : preparación de datos, métricas, núcleo de inferencia
  - integración : endpoints de la API sobre el modelo versionado real
  - funcionales : decisiones arquitectónicas del informe (AD1, AD3, AD4, RNF1)

No requieren events.csv: usan el modelo publicado en out/models, por eso corren en CI.

Ejecutar:  pytest -v tests_reco.py
"""
import os
import tempfile
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix

# Base de eventos temporal: los tests nunca escriben en la base real
os.environ["EVENTS_DB"] = os.path.join(tempfile.mkdtemp(), "eventos_test.db")

from fastapi.testclient import TestClient  # noqa: E402

import api as api_mod  # noqa: E402
from core import Recommender, default_model_root, resolve_current  # noqa: E402
from prepare_data import EVENT_WEIGHTS, build_matrix, filter_sparse, temporal_split  # noqa: E402
from train_evaluate import PopularityModel, precision_recall_map  # noqa: E402

UNKNOWN_USER = 999999999999


@pytest.fixture(scope="module")
def rec():
    return Recommender(resolve_current(default_model_root()))


@pytest.fixture(scope="module")
def client():
    with TestClient(api_mod.app) as c:
        yield c


@pytest.fixture(scope="module")
def known_users(rec):
    return list(rec.uidx.keys())[:300]


# ======================================================================
# UNITARIOS — preparación de datos
# ======================================================================
def test_pesos_de_eventos_ordenados():
    assert EVENT_WEIGHTS["purchase"] > EVENT_WEIGHTS["cart"] > EVENT_WEIGHTS["view"]


def test_split_temporal_no_filtra_futuro():
    """El train nunca puede contener eventos posteriores al test (fuga de datos)."""
    df = pd.DataFrame({
        "event_time": pd.to_datetime(["2021-01-01", "2021-01-05", "2021-01-10", "2021-01-20", "2021-01-30"], utc=True),
        "user_id": [1, 2, 3, 4, 5], "product_id": [10, 20, 30, 40, 50], "event_type": ["view"] * 5,
    })
    train, test, _ = temporal_split(df, test_fraction=0.4)
    assert len(train) and len(test)
    assert train.event_time.max() <= test.event_time.min()


def test_filtro_elimina_usuarios_con_poca_senal():
    df = pd.DataFrame({"user_id": [1] * 6 + [2], "product_id": [100, 101, 102, 103, 104, 105, 100],
                       "event_type": ["view"] * 7})
    assert 2 not in filter_sparse(df, min_user=5, min_item=1).user_id.values


def test_matriz_agrega_pesos_del_mismo_par():
    df = pd.DataFrame({"user_id": [1, 1, 1], "product_id": [100, 100, 100],
                       "event_type": ["view", "cart", "purchase"]})
    mat, uidx, iidx, _, _ = build_matrix(df)
    assert mat[uidx[1], iidx[100]] == pytest.approx(sum(EVENT_WEIGHTS.values()))


# ======================================================================
# UNITARIOS — métricas
# ======================================================================
def test_precision_perfecta():
    assert precision_recall_map([1, 2, 3], {1, 2, 3}, k=3) == pytest.approx((1.0, 1.0, 1.0))


def test_precision_nula():
    assert precision_recall_map([9, 8, 7], {1, 2, 3}, k=3) == (0.0, 0.0, 0.0)


def test_map_premia_los_aciertos_arriba():
    assert precision_recall_map([1, 9, 8], {1}, k=3)[2] > precision_recall_map([9, 8, 1], {1}, k=3)[2]


def test_sin_relevantes_devuelve_none():
    assert precision_recall_map([1, 2], set(), k=2) is None


def test_popularidad_ordena_y_no_repite_lo_visto():
    mat = csr_matrix(np.array([[1, 0, 5], [2, 0, 5], [0, 1, 0]], dtype=np.float32))
    pop = PopularityModel().fit(mat)
    assert pop.ranking[0] == 2
    assert 2 not in pop.recommend(None, seen={2}, k=2)


# ======================================================================
# UNITARIOS — núcleo de inferencia (core.py)
# ======================================================================
def test_core_no_recomienda_productos_ya_vistos(rec, known_users):
    u = known_users[0]
    seen = {int(rec.item_ids[i]) for i in rec.user_items[rec.uidx[u]].indices}
    recs = {p for p, _ in rec.personalized(u, 20)}
    assert seen and not (recs & seen)


def test_core_usuario_desconocido_devuelve_none(rec):
    assert rec.personalized(UNKNOWN_USER, 10) is None


def test_core_fallback_nunca_vacio(rec):
    assert len(rec.fallback(10)) == 10


def test_modelo_usa_formato_portable():
    """El modelo se guarda como npz + json, no pickle (seguridad y compatibilidad)."""
    files = set(os.listdir(resolve_current(default_model_root())))
    assert {"factors.npz", "meta.json"} <= files
    assert not any(f.endswith(".pkl") for f in files)


# ======================================================================
# INTEGRACIÓN — API
# ======================================================================
def test_salud(client):
    assert client.get("/salud").json()["estado"] == "ok"


def test_recomendacion_personalizada_con_metadatos(client, known_users):
    body = client.get(f"/recomendaciones?user_id={known_users[1]}&k=10").json()
    assert body["source"] in ("model", "cache")
    assert len(body["recommendations"]) == 10
    assert all("categoria" in p and "precio" in p for p in body["recommendations"])


def test_user_id_se_devuelve_exacto_como_texto(client, known_users):
    """Los IDs superan el entero seguro de JavaScript: deben viajar como texto sin redondeo."""
    u = known_users[2]
    assert client.get(f"/recomendaciones?user_id={u}").json()["user_id"] == str(u)


def test_scores_ordenados_y_sin_duplicados(client, known_users):
    recs = client.get(f"/recomendaciones?user_id={known_users[3]}&k=20").json()["recommendations"]
    scores = [p["score"] for p in recs]
    ids = [p["product_id"] for p in recs]
    assert scores == sorted(scores, reverse=True)
    assert len(ids) == len(set(ids))


def test_parametros_invalidos(client, known_users):
    assert client.get(f"/recomendaciones?user_id={known_users[0]}&k=0").status_code == 400
    assert client.get(f"/recomendaciones?user_id={known_users[0]}&k=51").status_code == 400
    assert client.get("/recomendaciones?user_id=abc").status_code == 422


def test_modelo_expone_version_y_metricas(client):
    m = client.get("/modelo").json()
    assert m["version"].startswith("v")
    assert m["metricas_offline"]["map@10"] > m["baseline_popularidad"]["map@10"]


def test_dashboard_se_sirve(client):
    r = client.get("/dashboard")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_autenticacion_rechaza_sin_token(client, known_users, monkeypatch):
    monkeypatch.setattr(api_mod, "API_TOKEN", "secreto-de-prueba")
    assert client.get(f"/recomendaciones?user_id={known_users[0]}").status_code == 401
    ok = client.get(f"/recomendaciones?user_id={known_users[0]}",
                    headers={"Authorization": "Bearer secreto-de-prueba"})
    assert ok.status_code == 200
    assert client.get("/salud").status_code == 200  # el health check sigue público


# ======================================================================
# FUNCIONALES — decisiones arquitectónicas
# ======================================================================
def test_AD3_cold_start_activa_fallback(client):
    body = client.get(f"/recomendaciones?user_id={UNKNOWN_USER}&k=10").json()
    assert body["source"] == "fallback" and len(body["recommendations"]) == 10


def test_AD1_segunda_llamada_sale_de_cache(client, known_users):
    client.get(f"/recomendaciones?user_id={known_users[4]}&k=7")
    assert client.get(f"/recomendaciones?user_id={known_users[4]}&k=7").json()["source"] == "cache"


def test_evento_se_persiste_e_invalida_cache(client, known_users):
    import sqlite3
    u = known_users[5]
    client.get(f"/recomendaciones?user_id={u}&k=5")
    assert client.get(f"/recomendaciones?user_id={u}&k=5").json()["source"] == "cache"

    r = client.post("/eventos", json={"user_id": str(u), "product_id": 123, "event_type": "purchase"})
    assert r.status_code == 201

    with sqlite3.connect(os.environ["EVENTS_DB"]) as con:
        assert con.execute("SELECT COUNT(*) FROM eventos WHERE user_id=?", (u,)).fetchone()[0] == 1
    # tras el evento, la recomendación vuelve a calcularse con el modelo
    assert client.get(f"/recomendaciones?user_id={u}&k=5").json()["source"] == "model"


def test_evento_con_tipo_invalido_se_rechaza(client):
    r = client.post("/eventos", json={"user_id": 1, "product_id": 1, "event_type": "robo"})
    assert r.status_code == 422


def test_RNF1_latencia_p95_bajo_200ms(client, known_users):
    lat = [client.get(f"/recomendaciones?user_id={u}&k=10").json()["latency_ms"] for u in known_users[10:210]]
    assert float(np.percentile(lat, 95)) < 200


def test_metricas_de_observabilidad(client):
    m = client.get("/metricas").json()
    for campo in ("latencia_ms", "tasa_error", "tasa_fallback", "tasa_cache_hit", "solicitudes_totales"):
        assert campo in m
    assert {"p50", "p95", "p99"} <= set(m["latencia_ms"])
