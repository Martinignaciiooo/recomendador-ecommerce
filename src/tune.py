"""Barrido de hiperparámetros del modelo ALS y medición de latencia por solicitud."""
import pickle, os, time, json
import numpy as np
from train_evaluate import ALSModel, evaluate, K

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(base, "out")

with open(os.path.join(out, "dataset.pkl"), "rb") as f:
    data = pickle.load(f)
mat = data["matrix"]

grid = [
    {"factors": 32,  "regularization": 0.05, "iterations": 20, "alpha": 40},
    {"factors": 64,  "regularization": 0.05, "iterations": 20, "alpha": 40},
    {"factors": 128, "regularization": 0.05, "iterations": 20, "alpha": 40},
    {"factors": 64,  "regularization": 0.01, "iterations": 20, "alpha": 40},
    {"factors": 64,  "regularization": 0.10, "iterations": 20, "alpha": 40},
    {"factors": 64,  "regularization": 0.05, "iterations": 30, "alpha": 15},
    {"factors": 64,  "regularization": 0.05, "iterations": 30, "alpha": 100},
    {"factors": 96,  "regularization": 0.05, "iterations": 30, "alpha": 40},
]

print(f"{'factors':>8}{'reg':>7}{'iters':>7}{'alpha':>7}{'Prec@10':>10}{'Recall@10':>11}{'MAP@10':>9}{'Cob.':>8}")
print("-" * 67)

rows, best, best_map = [], None, -1
for g in grid:
    m = ALSModel(**g).fit(mat)
    r = evaluate(m, data, batch=True)
    rows.append({**g, **r})
    print(f"{g['factors']:>8}{g['regularization']:>7}{g['iterations']:>7}{g['alpha']:>7}"
          f"{r['precision@10']:>10.4f}{r['recall@10']:>11.4f}{r['map@10']:>9.4f}"
          f"{r['cobertura_catalogo']:>7.1%}")
    if r["map@10"] > best_map:
        best_map, best, best_cfg = r["map@10"], m, g

print("-" * 67)
print(f"Mejor configuración por MAP@10: {best_cfg}")

# ---- latencia de una sola solicitud (caso API en producción) ----
uidx = data["uidx"]
sample = list(uidx.values())[:500]
lat = []
for u in sample:
    t0 = time.perf_counter()
    best.model.recommend(u, mat[u], N=K, filter_already_liked_items=True)
    lat.append((time.perf_counter() - t0) * 1000)

lat = np.array(lat)
print(f"\nLatencia de inferencia por solicitud (n={len(lat)}):")
print(f"  media : {lat.mean():.3f} ms")
print(f"  p50   : {np.percentile(lat,50):.3f} ms")
print(f"  p95   : {np.percentile(lat,95):.3f} ms")
print(f"  p99   : {np.percentile(lat,99):.3f} ms")
print(f"  max   : {lat.max():.3f} ms")
print(f"\nPresupuesto del caso: 200 ms  ->  margen restante p95: {200 - np.percentile(lat,95):.1f} ms")

with open(os.path.join(out, "sweep.json"), "w") as f:
    json.dump({"grid": rows, "best": best_cfg,
               "latencia_ms": {"media": float(lat.mean()),
                               "p50": float(np.percentile(lat,50)),
                               "p95": float(np.percentile(lat,95)),
                               "p99": float(np.percentile(lat,99))}},
              f, indent=2, ensure_ascii=False)
print(f"\nBarrido guardado en {out}/sweep.json  (el modelo de producción lo genera train_final.py)")
