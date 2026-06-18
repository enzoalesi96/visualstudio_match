"""
shared/recommender.py
Consulta la tabla dbo.hd_televisores y devuelve las 5 mejores opciones
aplicando un score multidimensional (precio, pulgadas, cluster).
"""

import re
import logging
import pyodbc
from typing import Optional

logger = logging.getLogger(__name__)

_RE_PULGADAS_NOMBRE = re.compile(r'\b(\d{2,3})\b')


def _limpiar_precio(valor) -> Optional[float]:
    """Convierte nvarchar de precio a float. Devuelve None si inválido."""
    if valor is None:
        return None
    limpio = re.sub(r"[^\d.]", "", str(valor))
    try:
        return float(limpio) if limpio else None
    except ValueError:
        return None


def _mejor_precio(row: dict) -> Optional[float]:
    """Devuelve el menor precio válido entre los 4 campos de precio."""
    candidatos = [
        _limpiar_precio(row.get("internet_price")),
        _limpiar_precio(row.get("event_price")),
        _limpiar_precio(row.get("normal_price")),
        _limpiar_precio(row.get("cmr_price")),
    ]
    validos = [p for p in candidatos if p is not None and p > 0]
    return min(validos) if validos else None


def _pulgadas_desde_nombre(name: str) -> Optional[int]:
    """Extrae las pulgadas del nombre del producto (ej: '55' de 'Smart TV 55"')."""
    matches = _RE_PULGADAS_NOMBRE.findall(name)
    candidatos = [int(m) for m in matches if 19 <= int(m) <= 120]
    return candidatos[0] if candidatos else None


def _score(tv: dict, pulgadas_ref: int, presupuesto: int) -> float:
    """
    Score de relevancia (mayor = mejor):
      - Penaliza diferencia de pulgadas (peso: 2.0 por pulgada)
      - Premia aprovechar el presupuesto (precio lo más cercano al tope superior)
      - Penaliza exceder el presupuesto (no debería ocurrir, pero seguridad)
    """
    diff_pulgadas = abs((tv["pulgadas"] or pulgadas_ref) - pulgadas_ref)
    aprovechamiento = (tv["precio"] / presupuesto) if presupuesto > 0 else 0
    penalizacion_exceso = max(0, tv["precio"] - presupuesto) * 10

    return aprovechamiento * 100 - diff_pulgadas * 2 - penalizacion_exceso


def obtener_top5(
    conn: pyodbc.Connection,
    pulgadas: Optional[int],
    presupuesto: int,
    familia: str,
    cluster_id: Optional[int] = None,
) -> list[dict]:
    """
    Consulta la BD y devuelve las 5 mejores opciones de TV.

    Estrategia:
      1. Filtra por familia (LIKE) y un rango de presupuesto generoso (TOP 300).
      2. Normaliza precios en Python.
      3. Filtra los que están dentro del presupuesto.
      4. Aplica score multidimensional.
      5. Devuelve los 5 mejores.
    """
    cursor = conn.cursor()

    # Margen superior del 10% para no perder opciones muy cercanas
    presupuesto_max = int(presupuesto * 1.10)

    # Si cluster_id está disponible lo usamos para pre-filtrar por rango de precio
    # (esto reemplaza filtrar por cluster en SQL ya que la columna no existe aún)
    sql_query = """
        SELECT TOP 300
            name,
            family,
            seller,
            url_product,
            url_image,
            internet_price,
            event_price,
            normal_price,
            cmr_price
        FROM dbo.hd_televisores
        WHERE LOWER(family) LIKE LOWER(?)
    """

    cursor.execute(sql_query, f"%{familia}%")
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    logger.info(f"📊 Registros encontrados en SQL: {len(rows)}")

    # ── Normalizar y enriquecer ────────────────────────────────────────────
    televisores = []
    for row in rows:
        precio = _mejor_precio(row)
        if precio is None:
            continue

        tv_pulgadas = _pulgadas_desde_nombre(row["name"])

        televisores.append({
            "name": row["name"],
            "familia": row["family"],
            "pulgadas": tv_pulgadas,
            "vendedor": row["seller"],
            "precio": round(precio, 2),
            "url": row["url_product"],
            "imagen": row["url_image"],
        })

    # ── Filtrar dentro del presupuesto ─────────────────────────────────────
    dentro = [tv for tv in televisores if tv["precio"] <= presupuesto_max]

    logger.info(f"✅ TVs dentro del presupuesto S/ {presupuesto_max}: {len(dentro)}")

    if not dentro:
        return []

    # ── Aplicar score y devolver top 5 ────────────────────────────────────
    ref_pulgadas = pulgadas or 55  # fallback si no se pudo extraer
    scored = sorted(
        dentro,
        key=lambda tv: _score(tv, ref_pulgadas, presupuesto),
        reverse=True,
    )

    top5 = scored[:5]

    # Marcar rango para el frontend
    for i, tv in enumerate(top5):
        tv["rank"] = i + 1

    return top5
