"""
Punto de entrada de inferencia para AWS SageMaker (contenedor SKLearn).

SageMaker llama a estas cuatro funciones. La lógica de recomendación vive en
core.py, el mismo módulo que usa la API: una sola implementación para ambos.
"""
import json

from core import Recommender


def model_fn(model_dir):
    """Carga el modelo desde /opt/ml/model (factors.npz + meta.json)."""
    return Recommender(model_dir)


def input_fn(body, content_type):
    if content_type != "application/json":
        raise ValueError(f"Content-Type no soportado: {content_type}")
    return json.loads(body)


def predict_fn(data, rec):
    user_id = int(data["user_id"])
    k = max(1, min(int(data.get("k", 10)), 50))
    pairs = rec.personalized(user_id, k)
    source = "model"
    if pairs is None:
        pairs, source = rec.fallback(k), "fallback"
    return {
        "user_id": str(user_id),
        "source": source,
        "model_version": rec.version,
        "recommendations": [{"product_id": p, "score": round(s, 5), **rec.describe(p)} for p, s in pairs],
    }


def output_fn(prediction, accept):
    return json.dumps(prediction, ensure_ascii=False), "application/json"
