"""
shared/clustering.py
Carga el modelo KMeans pre-entrenado y asigna un cluster al input del usuario.
El modelo se genera con training/train_kmeans.py y se incluye en el deploy.
"""

import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# Ruta al modelo: mismo directorio que este archivo
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "kmeans_model.pkl")

# Cache en memoria para no recargar en cada invocación (warm instance)
_model_cache = None
_scaler_cache = None


def _cargar_modelo():
    """Carga joblib.load con lazy loading + cache."""
    global _model_cache, _scaler_cache
    if _model_cache is not None:
        return _model_cache, _scaler_cache

    try:
        import joblib
        data = joblib.load(_MODEL_PATH)
        _model_cache = data["kmeans"]
        _scaler_cache = data["scaler"]
        logger.info(f"✅ Modelo KMeans cargado — {_model_cache.n_clusters} clusters")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo cargar el modelo KMeans: {e}. Usando cluster=0.")
        _model_cache = None
        _scaler_cache = None

    return _model_cache, _scaler_cache


# Mapeo familia → valor numérico para el modelo
_FAMILIA_NUM = {
    "LED":      0,
    "QLED":     1,
    "OLED":     2,
    "NanoCell": 3,
}


def aplicar_cluster(
    pulgadas: Optional[int],
    presupuesto: Optional[int],
    familia: Optional[str],
) -> Optional[int]:
    """
    Convierte los inputs del usuario en un vector de features y predice el cluster.

    Features usadas (alineadas con train_kmeans.py):
        [pulgadas, presupuesto, familia_num]

    Devuelve el cluster_id (int) o None si el modelo no está disponible.
    """
    kmeans, scaler = _cargar_modelo()

    if kmeans is None:
        return None

    pulgadas_val = pulgadas or 55
    presupuesto_val = presupuesto or 2000
    familia_num = _FAMILIA_NUM.get(familia or "LED", 0)

    features = np.array([[pulgadas_val, presupuesto_val, familia_num]], dtype=float)

    if scaler is not None:
        features = scaler.transform(features)

    cluster_id = int(kmeans.predict(features)[0])
    logger.info(f"🎯 Cluster predicho: {cluster_id} para features {[pulgadas_val, presupuesto_val, familia_num]}")

    return cluster_id
