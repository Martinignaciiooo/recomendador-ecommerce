"""
Núcleo de inferencia del recomendador.

Lo usan tanto la API (FastAPI en EC2) como el endpoint de SageMaker, para que
exista una sola implementación de la lógica de recomendación.

Solo depende de numpy y scipy: la inferencia de ALS es un producto punto entre
el vector del usuario y los vectores de los productos, no necesita la librería
de entrenamiento.

El modelo se guarda como factors.npz + meta.json (no pickle). Motivo: pickle
ejecuta código al cargarse y se rompe entre versiones de numpy; npz y json no.
"""
import json
import os

import numpy as np
from scipy.sparse import csr_matrix


class Recommender:
    def __init__(self, model_dir):
        z = np.load(os.path.join(model_dir, "factors.npz"), allow_pickle=False)
        self.user_factors = z["user_factors"]
        self.item_factors = z["item_factors"]
        self.item_ids = z["item_ids"]
        self.uidx = {int(u): i for i, u in enumerate(z["user_ids"])}
        # Productos con los que cada usuario ya interactuó (para no repetirlos)
        self.user_items = csr_matrix(
            (z["ui_data"], z["ui_indices"], z["ui_indptr"]), shape=tuple(z["ui_shape"])
        )
        with open(os.path.join(model_dir, "meta.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self.version = self.meta["version"]
        self.popular = [int(p) for p in self.meta["popular"]]
        self.catalog = {int(k): v for k, v in self.meta["catalog"].items()}

    def knows(self, user_id):
        return user_id in self.uidx

    def personalized(self, user_id, k):
        """Top-k personalizado. Devuelve None si el usuario no está en el modelo."""
        row = self.uidx.get(user_id)
        if row is None:
            return None
        scores = self.item_factors @ self.user_factors[row]
        seen = self.user_items[row].indices
        if len(seen):
            scores[seen] = -np.inf
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(self.item_ids[i]), float(scores[i])) for i in top if np.isfinite(scores[i])]

    def fallback(self, k):
        """Productos más vendidos: garantiza que nunca se devuelva una lista vacía."""
        return [(p, 0.0) for p in self.popular[:k]]

    def describe(self, product_id):
        return self.catalog.get(product_id, {})


def resolve_current(model_root):
    """Lee el puntero 'current' del registro de modelos y devuelve la carpeta activa."""
    with open(os.path.join(model_root, "current"), encoding="utf-8") as f:
        version = f.read().strip()
    return os.path.join(model_root, version)


def default_model_root():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.environ.get("MODEL_ROOT", os.path.join(base, "out", "models"))
