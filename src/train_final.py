"""
Entrenamiento de producción con registro de versiones (decisión AD4).

1. Entrena ALS con la mejor configuración del barrido (sweep.json).
2. Guarda el modelo como una versión nueva en el registro: out/models/vYYYYMMDD-HHMMSS/
3. Compara el modelo nuevo (challenger) contra el vigente (champion) sobre el MISMO
   periodo de test y los mismos usuarios, usando el mismo código que la API.
4. Solo mueve el puntero 'current' si el nuevo no empeora más que la tolerancia.

Si el nuevo es peor, queda guardado pero no se activa: el servicio sigue con el anterior.

Uso:  python train_final.py [--force] [--tolerancia 0.05]
"""
import argparse
import datetime as dt
import json
import os
import pickle

import numpy as np
import pandas as pd

from core import Recommender, resolve_current, default_model_root
from train_evaluate import ALSModel, PopularityModel, evaluate, precision_recall_map, K

DEFAULT_CFG = {"factors": 32, "regularization": 0.05, "iterations": 20, "alpha": 40}


def build_catalog(train, items):
    """Metadatos legibles por producto: dan interpretabilidad a la recomendación."""
    last = train.sort_values("event_time").groupby("product_id").last()
    catalog = {}
    for pid in items:
        r = last.loc[pid]
        catalog[str(int(pid))] = {
            "categoria": None if pd.isna(r["category_code"]) else str(r["category_code"]),
            "marca": None if pd.isna(r["brand"]) else str(r["brand"]),
            "precio": round(float(r["price"]), 2),
        }
    return catalog


def build_popular(train, n=100):
    """Productos más comprados en el periodo de entrenamiento (fallback, AD3)."""
    compras = train[train["event_type"] == "purchase"].groupby("product_id").size()
    popular = list(compras.sort_values(ascending=False).index[:n])
    if len(popular) < n:  # completar con los más vistos si hay pocas compras
        vistas = train.groupby("product_id").size().sort_values(ascending=False)
        popular += [p for p in vistas.index if p not in set(popular)][: n - len(popular)]
    return [int(p) for p in popular]


def save_version(model_root, version, model, data, meta):
    path = os.path.join(model_root, version)
    os.makedirs(path, exist_ok=True)
    ui = data["matrix"].tocsr()
    np.savez_compressed(
        os.path.join(path, "factors.npz"),
        user_factors=np.asarray(model.model.user_factors, dtype=np.float32),
        item_factors=np.asarray(model.model.item_factors, dtype=np.float32),
        user_ids=np.asarray(data["users"], dtype=np.int64),
        item_ids=np.asarray(data["items"], dtype=np.int64),
        ui_data=ui.data.astype(np.float32),
        ui_indices=ui.indices.astype(np.int32),
        ui_indptr=ui.indptr.astype(np.int64),
        ui_shape=np.asarray(ui.shape, dtype=np.int64),
    )
    with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return path


def evaluate_recommender(rec, test, users, k=K):
    """Evalúa un modelo guardado usando el mismo código de inferencia que la API."""
    truth = test.groupby("user_id")["product_id"].apply(lambda s: set(int(x) for x in s)).to_dict()
    P, R, A = [], [], []
    for u in users:
        recs = [p for p, _ in (rec.personalized(int(u), k) or [])]
        m = precision_recall_map(recs, truth.get(u, set()), k)
        if m:
            P.append(m[0]); R.append(m[1]); A.append(m[2])
    return {"usuarios": len(P), "precision@10": float(np.mean(P)) if P else 0.0,
            "recall@10": float(np.mean(R)) if R else 0.0, "map@10": float(np.mean(A)) if A else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="promover aunque empeore")
    ap.add_argument("--tolerancia", type=float, default=0.05,
                    help="caída máxima de MAP@10 aceptada (0.05 = 5%%)")
    args = ap.parse_args()

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(base, "out")
    model_root = default_model_root()
    os.makedirs(model_root, exist_ok=True)

    with open(os.path.join(out, "dataset.pkl"), "rb") as f:
        data = pickle.load(f)

    cfg = DEFAULT_CFG
    sweep_path = os.path.join(out, "sweep.json")
    if os.path.exists(sweep_path):
        with open(sweep_path, encoding="utf-8") as f:
            cfg = json.load(f)["best"]
    print(f"Configuración: {cfg}")

    model = ALSModel(**cfg).fit(data["matrix"])
    offline = evaluate(model, data, batch=True)
    baseline = evaluate(PopularityModel().fit(data["matrix"]), data)
    print(f"Challenger  MAP@10={offline['map@10']:.4f}  Prec@10={offline['precision@10']:.4f}  "
          f"Recall@10={offline['recall@10']:.4f}")
    print(f"Baseline    MAP@10={baseline['map@10']:.4f}  (popularidad)")

    version = "v" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    meta = {
        "version": version,
        "entrenado_en": dt.datetime.now().isoformat(timespec="seconds"),
        "algoritmo": "ALS (implicit)",
        "config": cfg,
        "corte_temporal": str(data["cutoff"]),
        "dimensiones": {"usuarios": int(data["matrix"].shape[0]), "productos": int(data["matrix"].shape[1]),
                        "interacciones": int(data["matrix"].nnz)},
        "metricas_offline": {k: offline[k] for k in ("precision@10", "recall@10", "map@10", "cobertura_catalogo")},
        "baseline_popularidad": {k: baseline[k] for k in ("precision@10", "recall@10", "map@10", "cobertura_catalogo")},
        "usuarios_test": offline["usuarios_evaluados"],
        "popular": build_popular(data["train"]),
        "catalog": build_catalog(data["train"], data["items"]),
    }
    path = save_version(model_root, version, model, data, meta)
    print(f"Versión guardada: {path}")

    # ---- champion vs challenger sobre el mismo test y los mismos usuarios ----
    current_file = os.path.join(model_root, "current")
    promote, motivo = True, "no existía un modelo vigente"
    if os.path.exists(current_file) and not args.force:
        champion = Recommender(resolve_current(model_root))
        challenger = Recommender(path)
        test = data["test"]
        users = [u for u in test["user_id"].unique() if champion.knows(int(u)) and challenger.knows(int(u))]
        m_old = evaluate_recommender(champion, test, users)
        m_new = evaluate_recommender(challenger, test, users)
        print(f"\nComparación sobre {m_new['usuarios']:,} usuarios comunes:")
        print(f"  vigente    {champion.version}: MAP@10={m_old['map@10']:.4f}")
        print(f"  candidato  {version}: MAP@10={m_new['map@10']:.4f}")
        umbral = m_old["map@10"] * (1 - args.tolerancia)
        promote = m_new["map@10"] >= umbral
        motivo = (f"MAP {m_new['map@10']:.4f} >= umbral {umbral:.4f}" if promote
                  else f"MAP {m_new['map@10']:.4f} < umbral {umbral:.4f}; se conserva {champion.version}")
    elif args.force:
        motivo = "promoción forzada (--force)"

    if promote:
        with open(current_file, "w", encoding="utf-8") as f:
            f.write(version)
        print(f"\nPROMOVIDO -> {version}  ({motivo})")
    else:
        print(f"\nNO PROMOVIDO  ({motivo})")


if __name__ == "__main__":
    main()
