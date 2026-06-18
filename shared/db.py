"""
shared/db.py
Conexión a Azure SQL Database usando pyodbc.
Las credenciales se leen de variables de entorno (Azure Function App Settings).
"""

import os
import pyodbc
import logging

logger = logging.getLogger(__name__)

# Driver disponible en Azure Functions Linux Python runtime
_DRIVER = "{ODBC Driver 18 for SQL Server}"


def conectar_sql() -> pyodbc.Connection:
    """
    Abre y devuelve una conexión a Azure SQL.
    Lanza excepción si las variables de entorno no están configuradas.
    """
    server = os.environ["SQL_SERVER"]       # ej: mi-server.database.windows.net
    database = os.environ["SQL_DATABASE"]   # ej: visionmatch
    user = os.environ["SQL_USER"]
    password = os.environ["SQL_PASSWORD"]

    conn_str = (
        f"DRIVER={_DRIVER};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    conn = pyodbc.connect(conn_str)
    logger.info("✅ Conexión Azure SQL exitosa")
    return conn


def cerrar_sql(conn: pyodbc.Connection) -> None:
    """Cierra la conexión de forma segura."""
    try:
        conn.close()
    except Exception:
        pass
