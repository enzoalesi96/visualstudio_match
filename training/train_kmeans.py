"""
training/train_kmeans.py
=======================
Script LOCAL para entrenar el modelo KMeans sobre el catálogo de televisores.
Se ejecuta una vez (o cuando el catálogo cambia significativamente) y genera
el archivo model/kmeans_model.pkl que se incluye en el deploy de la Function.

Uso:
    cd visionmatch-python/
    pip install scikit-learn joblib pyodbc python-dotenv
    python training/train_kmeans.py

Variables de entorno necesarias (en .env o entorno local):
    SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD
"""

import os
import re
import sys
import logging
import numpy as np
import pyodbc
import joblib

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from dotenv import load_dotenv

# ── Configuración ──────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

MODEL_OUTPUT = os.path.join(os.path.dirname(__file__), "..", "model", "kmeans_model.pkl")
N_CLUSTERS_DEFAULT = 4      # Ajustar según tamaño del catálogo
RANDOM_STATE = 42

_FAMILIA_NUM = {"LED": 0, "QLED": 1, "OLED": 2, "NanoCell": 3}
_RE_PULGADAS = re.compile(r'\b(\d{2,3})\b')


def limpiar_precio(valor) -> float | None:
    if not valor:
        return None
    limpio = re.sub(r"[^\d.]", "", str(valor))
    try:
        return float(limpio) if limpio else None
    except ValueError:
        return None


def mejor_precio(row: dict) -> float | None:
    precios = [
        limpiar_precio(row.get("internet_price")),
        limpiar_precio(row.get("event_price")),
        limpiar_precio(row.get("normal_price")),
        limpiar_precio(row.get("cmr_price")),
    ]
    validos = [p for p in precios if p and p > 0]
    return min(validos) if validos else None


def pulgadas_nombre(name: str) -> int | None:
    matches = [int(m) for m in _RE_PULGADAS.findall(name) if 19 <= int(m) <= 120]
    return matches[0] if matches else None


def familia_num(family: str) -> int:
    key = family.strip().upper()
    for k, v in _FAMILIA_NUM.items():
        if k.upper() in key:
            return v
    return 0


# ── Conexión SQL ────────────────────────────────────────────────────────────
def conectar():
    driver = "{ODBC Driver 18 for SQL Server}"
    conn_str = (
        f"DRIVER={driver};"
        f"SERVER={os.environ['SQL_SERVER']},1433;"
        f"DATABASE={os.environ['SQL_DATABASE']};"
        f"UID={os.environ['SQL_USER']};"
        f"PWD={os.environ['SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


# ── Cargar datos ────────────────────────────────────────────────────────────
def cargar_datos(conn) -> np.ndarray:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, family, internet_price, event_price, normal_price, cmr_price
        FROM dbo.hd_televisores
    """)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    logger.info(f"📊 Total registros: {len(rows)}")

    X = []
    for row in rows:
        precio = mejor_precio(row)
        pulgadas = pulgadas_nombre(row.get("name", ""))
        fnum = familia_num(row.get("family", ""))

        if precio is None or pulgadas is None:
            continue

        X.append([pulgadas, precio, fnum])

    logger.info(f"✅ Registros usables para training: {len(X)}")
    return np.array(X, dtype=float)


# ── Buscar k óptimo ─────────────────────────────────────────────────────────
def buscar_k_optimo(X_scaled: np.ndarray, k_min: int = 2, k_max: int = 8) -> int:
    """Usa silhouette score para elegir el mejor k."""
    scores = {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        scores[k] = score
        logger.info(f"  k={k}  silhouette={score:.4f}")

    mejor_k = max(scores, key=scores.get)
    logger.info(f"🏆 Mejor k: {mejor_k} (silhouette={scores[mejor_k]:.4f})")
    return mejor_k


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("🚀 Iniciando entrenamiento KMeans...")

    conn = conectar()
    logger.info("✅ Conexión SQL exitosa")

    X = cargar_datos(conn)
    conn.close()

    if len(X) < 10:
        logger.error("❌ Datos insuficientes para entrenar.")
        sys.exit(1)

    # Escalar features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Buscar k óptimo
    logger.info("\n🔍 Buscando k óptimo (silhouette)...")
    k = buscar_k_optimo(X_scaled)

    # Entrenar modelo final
    kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=20)
    kmeans.fit(X_scaled)

    logger.info(f"\n✅ Modelo entrenado — {k} clusters")
    logger.info(f"   Inertia: {kmeans.inertia_:.2f}")

    # Guardar
    os.makedirs(os.path.dirname(MODEL_OUTPUT), exist_ok=True)
    joblib.dump({"kmeans": kmeans, "scaler": scaler, "k": k}, MODEL_OUTPUT)
    logger.info(f"💾 Modelo guardado en: {MODEL_OUTPUT}")

    # Distribución de clusters
    from collections import Counter
    labels = kmeans.labels_
    dist = Counter(labels)
    logger.info("\n📊 Distribución de clusters:")
    for cluster_id, count in sorted(dist.items()):
        logger.info(f"   Cluster {cluster_id}: {count} TVs")


if __name__ == "__main__":
    main()
