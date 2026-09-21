"""
Entrenamiento y evaluación de modelos de recomendación.

Compara tres enfoques sobre el mismo split temporal:
  1. Popularidad (baseline)  - lo que recomendaría el sistema sin personalización
  2. Item-item CF (coseno)   - filtrado colaborativo basado en similitud de productos
  3. ALS (implicit)          - factorización matricial para feedback implícito

La baseline importa: si el modelo personalizado no la supera, no justifica su costo.
"""
import pickle
import os
import time
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize

K = 10  # tamaño de la lista de recomendaciones


# ----------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------
class PopularityModel:
    """Recomienda los productos más populares. Es también el fallback en producción."""

    name = "Popularidad (baseline)"

    def fit(self, mat):
        self.scores = np.asarray(mat.sum(axis=0)).ravel()
        self.ranking = np.argsort(-self.scores)
        return self

    def recommend(self, user_row, seen, k=K):
        out = [i for i in self.ranking if i not in seen][:k]
        return out


class ItemItemCF:
    """Similitud coseno entre productos a partir de la co-ocurrencia de usuarios."""

    name = "Item-item CF (coseno)"

    def __init__(self, shrink=10.0, topk_neighbors=200):
        self.shrink = shrink
        self.topk_neighbors = topk_neighbors

    def fit(self, mat):
        # Normalizar columnas -> el producto punto es la similitud coseno
        norm_items = normalize(mat.T.tocsr(), norm="l2", axis=1)
        sim = norm_items @ norm_items.T
        sim.setdiag(0)
        sim.eliminate_zeros()

        # Conservar solo los vecinos más similares por producto (reduce ruido y memoria)
        sim = sim.tocsr()
        data, indices, indptr = [], [], [0]
        for i in range(sim.shape[0]):
            s, e = sim.indptr[i], sim.indptr[i + 1]
            row_data = sim.data[s:e]
            row_idx = sim.indices[s:e]
            if len(row_data) > self.topk_neighbors:
                keep = np.argpartition(-row_data, self.topk_neighbors)[: self.topk_neighbors]
                row_data, row_idx = row_data[keep], row_idx[keep]
            data.append(row_data)
            indices.append(row_idx)
            indptr.append(indptr[-1] + len(row_data))

        self.sim = csr_matrix(
            (np.concatenate(data), np.concatenate(indices), np.array(indptr)),
            shape=sim.shape,
        )
        return self

    def recommend(self, user_row, seen, k=K):
        scores = np.asarray((user_row @ self.sim).todense()).ravel()
        if seen:
            scores[list(seen)] = -np.inf
        top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
        top = top[np.argsort(-scores[top])]
        return [int(i) for i in top if np.isfinite(scores[i])]


class ALSModel:
    """Factorización matricial ALS para feedback implícito (Hu, Koren & Volinsky)."""

    name = "ALS (factorización matricial)"

    def __init__(self, factors=64, regularization=0.05, iterations=20, alpha=40):
        from implicit.als import AlternatingLeastSquares

        self.alpha = alpha
        self.model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            iterations=iterations,
            random_state=42,
        )

    def fit(self, mat):
        self.model.fit((mat * self.alpha).astype(np.float32), show_progress=False)
        return self

    def recommend_batch(self, user_ids, mat, k=K):
        ids, _ = self.model.recommend(
            user_ids, mat[user_ids], N=k, filter_already_liked_items=True
        )
        return ids


# ----------------------------------------------------------------------
# Métricas
# ----------------------------------------------------------------------
def precision_recall_map(recs, relevant, k=K):
    if not relevant:
        return None
    recs = recs[:k]
    hits = [1 if r in relevant else 0 for r in recs]
    n_hits = sum(hits)
    precision = n_hits / k
    recall = n_hits / len(relevant)
    # MAP@k
    ap, running = 0.0, 0
    for i, h in enumerate(hits):
        if h:
            running += 1
            ap += running / (i + 1)
    ap = ap / min(len(relevant), k)
    return precision, recall, ap


def evaluate(model, data, k=K, batch=False):
    mat = data["matrix"]
    uidx, iidx = data["uidx"], data["iidx"]
    test = data["test"]

    # Ground truth: productos con los que el usuario interactuó en el periodo de test
    truth = (
        test.assign(ii=test.product_id.map(iidx))
        .groupby("user_id")["ii"]
        .apply(lambda s: set(s.dropna().astype(int)))
        .to_dict()
    )

    P, R, A = [], [], []
    recommended_items = set()
    eval_users = [u for u in truth if u in uidx]

    t0 = time.time()
    if batch:
        rows = np.array([uidx[u] for u in eval_users])
        all_recs = model.recommend_batch(rows, mat, k=k)
        for u, recs in zip(eval_users, all_recs):
            recs = [int(x) for x in recs]
            recommended_items.update(recs)
            m = precision_recall_map(recs, truth[u], k)
            if m:
                P.append(m[0]); R.append(m[1]); A.append(m[2])
    else:
        for u in eval_users:
            row = mat[uidx[u]]
            seen = set(row.indices.tolist())
            recs = model.recommend(row, seen, k=k)
            recommended_items.update(recs)
            m = precision_recall_map(recs, truth[u], k)
            if m:
                P.append(m[0]); R.append(m[1]); A.append(m[2])
    elapsed = time.time() - t0

    n = len(P)
    return {
        "modelo": model.name,
        "usuarios_evaluados": n,
        f"precision@{k}": float(np.mean(P)) if n else 0.0,
        f"recall@{k}": float(np.mean(R)) if n else 0.0,
        f"map@{k}": float(np.mean(A)) if n else 0.0,
        "cobertura_catalogo": len(recommended_items) / mat.shape[1],
        "ms_por_usuario": (elapsed / n * 1000) if n else 0.0,
    }


# ----------------------------------------------------------------------
def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(base, "out")

    with open(os.path.join(out, "dataset.pkl"), "rb") as f:
        data = pickle.load(f)

    mat = data["matrix"]
    print(f"Matriz de entrenamiento: {mat.shape[0]:,} usuarios x {mat.shape[1]:,} productos")
    print(f"Densidad: {mat.nnz / (mat.shape[0] * mat.shape[1]):.6%}\n")

    results = []

    print("Entrenando Popularidad...")
    pop = PopularityModel().fit(mat)
    results.append(evaluate(pop, data))

    print("Entrenando Item-item CF...")
    t0 = time.time()
    cf = ItemItemCF().fit(mat)
    print(f"  entrenado en {time.time()-t0:.1f}s")
    results.append(evaluate(cf, data))

    print("Entrenando ALS...")
    t0 = time.time()
    als = ALSModel().fit(mat)
    print(f"  entrenado en {time.time()-t0:.1f}s")
    results.append(evaluate(als, data, batch=True))

    print("\n" + "=" * 92)
    print(f"{'Modelo':<34}{'Prec@10':>10}{'Recall@10':>12}{'MAP@10':>10}{'Cobertura':>12}{'ms/usuario':>13}")
    print("=" * 92)
    for r in results:
        print(
            f"{r['modelo']:<34}"
            f"{r['precision@10']:>10.4f}"
            f"{r['recall@10']:>12.4f}"
            f"{r['map@10']:>10.4f}"
            f"{r['cobertura_catalogo']:>11.1%}"
            f"{r['ms_por_usuario']:>13.2f}"
        )
    print("=" * 92)
    print(f"Usuarios evaluados: {results[0]['usuarios_evaluados']:,}")

    with open(os.path.join(out, "resultados.pkl"), "wb") as f:
        pickle.dump({"results": results, "models": {"pop": pop, "cf": cf}}, f)

    import json
    with open(os.path.join(out, "metricas.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nMétricas guardadas en {out}/metricas.json")


if __name__ == "__main__":
    main()
