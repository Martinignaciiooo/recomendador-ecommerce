"""
Preparación de datos para el sistema de recomendación.

Construye la matriz de interacciones usuario-producto a partir del clickstream,
aplicando pesos por tipo de evento y un split temporal (no aleatorio) para que
la evaluación refleje el uso real: entrenar con el pasado, predecir el futuro.
"""
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
import pickle
import os
import sqlite3

# Peso de cada tipo de evento como señal implícita de interés.
# Una compra pesa más que un carrito, y este más que una vista.
EVENT_WEIGHTS = {"view": 1.0, "cart": 3.0, "purchase": 5.0}

# Mínimo de interacciones para que un usuario/producto entre al modelo.
# El dataset es muy disperso: sin este filtro, el modelo aprende ruido.
MIN_USER_EVENTS = 5
MIN_ITEM_EVENTS = 5

# Proporción final del periodo que se reserva para test.
TEST_FRACTION = 0.2


def load_events(path):
    df = pd.read_csv(path)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    df = df.dropna(subset=["user_id", "product_id"])
    return df


def load_api_events(db_path):
    """Eventos registrados por la API en producción (POST /eventos).

    Se suman al histórico para que cada reentrenamiento aprenda de la actividad
    reciente. Si la base no existe (primera ejecución), no aporta nada.
    """
    if not db_path or not os.path.exists(db_path):
        return pd.DataFrame()
    with sqlite3.connect(db_path) as con:
        extra = pd.read_sql_query(
            "SELECT event_time, event_type, product_id, user_id FROM eventos", con
        )
    extra["event_time"] = pd.to_datetime(extra["event_time"], utc=True)
    return extra


def temporal_split(df, test_fraction=TEST_FRACTION):
    """Corta por fecha, no al azar: entrenamos con el pasado."""
    cutoff = df["event_time"].quantile(1 - test_fraction)
    train = df[df["event_time"] <= cutoff].copy()
    test = df[df["event_time"] > cutoff].copy()
    return train, test, cutoff


def filter_sparse(df, min_user=MIN_USER_EVENTS, min_item=MIN_ITEM_EVENTS):
    """Elimina iterativamente usuarios y productos con poca señal."""
    while True:
        n0 = len(df)
        uc = df.groupby("user_id")["product_id"].transform("size")
        df = df[uc >= min_user]
        ic = df.groupby("product_id")["user_id"].transform("size")
        df = df[ic >= min_item]
        if len(df) == n0 or len(df) == 0:
            break
    return df


def build_matrix(train):
    """Matriz dispersa usuario x producto con los pesos agregados."""
    train = train.copy()
    train["weight"] = train["event_type"].map(EVENT_WEIGHTS).fillna(1.0)

    agg = train.groupby(["user_id", "product_id"], as_index=False)["weight"].sum()

    users = np.sort(agg["user_id"].unique())
    items = np.sort(agg["product_id"].unique())
    uidx = {u: i for i, u in enumerate(users)}
    iidx = {p: i for i, p in enumerate(items)}

    rows = agg["user_id"].map(uidx).to_numpy()
    cols = agg["product_id"].map(iidx).to_numpy()
    vals = agg["weight"].to_numpy(dtype=np.float32)

    mat = csr_matrix((vals, (rows, cols)), shape=(len(users), len(items)))
    return mat, uidx, iidx, users, items


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(base, "data", "events.csv")
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)

    print("Cargando eventos...")
    df = load_events(src)
    db_path = os.environ.get("EVENTS_DB", os.path.join(out, "eventos.db"))
    extra = load_api_events(db_path)
    if len(extra):
        print(f"  + {len(extra):,} eventos registrados por la API ({db_path})")
        df = pd.concat([df, extra], ignore_index=True)
    print(f"  eventos totales: {len(df):,}")
    print(f"  usuarios: {df.user_id.nunique():,} | productos: {df.product_id.nunique():,}")

    train_raw, test_raw, cutoff = temporal_split(df)
    print(f"\nSplit temporal en {cutoff:%Y-%m-%d}")
    print(f"  train: {len(train_raw):,} eventos | test: {len(test_raw):,} eventos")

    print("\nFiltrando usuarios/productos con poca señal...")
    train = filter_sparse(train_raw)
    print(f"  train filtrado: {len(train):,} eventos")
    print(f"  usuarios: {train.user_id.nunique():,} | productos: {train.product_id.nunique():,}")

    mat, uidx, iidx, users, items = build_matrix(train)
    density = mat.nnz / (mat.shape[0] * mat.shape[1])
    print(f"\nMatriz: {mat.shape[0]:,} usuarios x {mat.shape[1]:,} productos")
    print(f"  interacciones no nulas: {mat.nnz:,}")
    print(f"  densidad: {density:.6%}")

    # El test solo conserva usuarios y productos vistos en entrenamiento:
    # evaluar sobre ítems que el modelo nunca vio no mide nada.
    test = test_raw[
        test_raw.user_id.isin(uidx.keys()) & test_raw.product_id.isin(iidx.keys())
    ].copy()
    print(f"\nTest evaluable: {len(test):,} eventos")
    print(f"  usuarios evaluables: {test.user_id.nunique():,}")

    with open(os.path.join(out, "dataset.pkl"), "wb") as f:
        pickle.dump(
            {
                "matrix": mat,
                "uidx": uidx,
                "iidx": iidx,
                "users": users,
                "items": items,
                "train": train,
                "test": test,
                "cutoff": cutoff,
            },
            f,
        )
    print(f"\nGuardado en {out}/dataset.pkl")


if __name__ == "__main__":
    main()
