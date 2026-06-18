import logging
import json
import azure.functions as func

from shared.parser import extraer_datos, tiene_info_suficiente
from shared.db import conectar_sql, cerrar_sql
from shared.recommender import obtener_top5
from shared.clustering import aplicar_cluster

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function HTTP trigger — endpoint /api/chat
    Recibe el mensaje del usuario y devuelve las 5 mejores opciones de TV.
    """
    logger.info("🔵 VisionMatch Function iniciada")

    # ── CORS preflight ──────────────────────────────────────────────────────
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers=_cors_headers(),
        )

    # ── Leer body ──────────────────────────────────────────────────────────
    try:
        body = req.get_json()
        message = body.get("message", "").strip()
    except Exception:
        return _json_response(
            {"info": "No se recibió un mensaje válido."},
            status=400,
        )

    logger.info(f"📩 Mensaje recibido: {message!r}")

    # ── Validación mínima ──────────────────────────────────────────────────
    if not message or not tiene_info_suficiente(message):
        return _json_response({
            "info": (
                "Hola 👋 soy VisionMatch AI. Para recomendarte el mejor televisor, "
                "indícame:\n"
                "  • Pulgadas\n"
                "  • Presupuesto (en soles)\n"
                "  • Familia (LED / QLED / OLED / NanoCell)\n\n"
                "Ejemplo:\n"
                "👉 55 pulgadas QLED hasta 3000 soles"
            )
        })

    # ── Extracción de parámetros ───────────────────────────────────────────
    datos = extraer_datos(message)
    pulgadas = datos["pulgadas"]
    presupuesto = datos["presupuesto"]
    familia = datos["familia"]

    logger.info(f"🔍 Extraído: {datos}")

    # ── Clustering KMeans ──────────────────────────────────────────────────
    cluster_id = aplicar_cluster(pulgadas, presupuesto, familia)
    logger.info(f"🎯 Cluster asignado: {cluster_id}")

    # ── Consulta SQL ───────────────────────────────────────────────────────
    pool = None
    try:
        pool = conectar_sql()

        top5 = obtener_top5(
            conn=pool,
            pulgadas=pulgadas,
            presupuesto=presupuesto,
            familia=familia,
            cluster_id=cluster_id,
        )

        if not top5:
            return _json_response({
                "info": (
                    f"❌ No encontramos televisores {familia.upper()} "
                    f"dentro del presupuesto de S/ {presupuesto}.\n"
                    "Intenta aumentar el presupuesto o cambiar la familia."
                )
            })

        return _json_response({
            "message": (
                f"📺 Aquí tus **5 mejores opciones** de TV {familia.upper()} "
                f"hasta S/ {presupuesto}, ordenadas por mejor relación precio/tamaño:"
            ),
            "products": top5,
            "cluster_id": cluster_id,
        })

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return _json_response({"error": str(e)}, status=500)

    finally:
        if pool:
            cerrar_sql(pool)
            logger.info("🔒 Conexión SQL cerrada")


# ── Helpers ────────────────────────────────────────────────────────────────

def _json_response(data: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(data, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
        headers=_cors_headers(),
    )


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
