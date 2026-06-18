"""
shared/parser.py
Extrae parámetros estructurados del mensaje libre del usuario.
"""

import re
from typing import Optional


# ── Mapeo de aliases de familia ────────────────────────────────────────────
_FAMILY_MAP = {
    "oled": "OLED",
    "qled": "QLED",
    "nanocell": "NanoCell",
    "nano cell": "NanoCell",
    "nano": "NanoCell",
    "led": "LED",
    "4k": "LED",       # si solo dice "4K" asumimos LED
    "full hd": "LED",
    "fullhd": "LED",
    "hd": "LED",
}

# ── Patrones regex ─────────────────────────────────────────────────────────
_RE_PULGADAS = re.compile(
    r'(\d{2,3})\s*(?:pulgadas|")',
    re.IGNORECASE,
)
_RE_PRESUPUESTO = re.compile(
    r'(?:hasta|menos\s+de|max(?:imo)?|presupuesto[:\s]+)?'
    r'(?:s/\.?\s*)?(\d{3,6})\s*(?:soles?|s/)?',
    re.IGNORECASE,
)
_RE_FAMILIA = re.compile(
    r'\b(oled|qled|nanocell|nano\s*cell|nano|led|4k|full\s*hd|fullhd|hd)\b',
    re.IGNORECASE,
)


def tiene_info_suficiente(message: str) -> bool:
    """Devuelve True si el mensaje contiene pulgadas, presupuesto Y familia."""
    tiene_pulgadas = bool(_RE_PULGADAS.search(message))
    tiene_presupuesto = bool(_RE_PRESUPUESTO.search(message))
    tiene_familia = bool(_RE_FAMILIA.search(message))
    return tiene_pulgadas and tiene_presupuesto and tiene_familia


def extraer_datos(message: str) -> dict:
    """
    Extrae y normaliza los parámetros del mensaje.
    Devuelve:
        {
            "pulgadas": int | None,
            "presupuesto": int | None,
            "familia": str | None,   # normalizado: "LED", "QLED", "OLED", "NanoCell"
            "familia_raw": str,      # lo que escribió el usuario
        }
    """
    pulgadas: Optional[int] = None
    presupuesto: Optional[int] = None
    familia: Optional[str] = None
    familia_raw: str = ""

    m_pulgadas = _RE_PULGADAS.search(message)
    if m_pulgadas:
        pulgadas = int(m_pulgadas.group(1))

    # Buscar todos los números de 3+ dígitos y tomar el mayor como presupuesto
    # (para evitar confundir el nro de pulgadas con el presupuesto)
    numeros_grandes = [
        int(n) for n in re.findall(r'\b(\d{3,6})\b', message)
        if int(n) > 99
    ]
    if pulgadas and pulgadas in numeros_grandes:
        numeros_grandes.remove(pulgadas)
    if numeros_grandes:
        presupuesto = max(numeros_grandes)

    m_familia = _RE_FAMILIA.search(message)
    if m_familia:
        familia_raw = m_familia.group(1).lower().replace(" ", "")
        familia = _FAMILY_MAP.get(familia_raw, "LED")

    return {
        "pulgadas": pulgadas,
        "presupuesto": presupuesto,
        "familia": familia,
        "familia_raw": familia_raw,
    }
