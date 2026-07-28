"""Modelos de datos compartidos por todos los scrapers."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Category:
    """Una categoría nativa de una cadena."""

    id: str
    name: str
    url: Optional[str] = None
    parent: Optional[str] = None  # nombre de la categoría padre (nivel 1)
    extra: dict = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.parent} > {self.name}" if self.parent else self.name


@dataclass
class Product:
    """Producto normalizado, común a todas las cadenas."""

    cadena: str
    nombre: str
    marca: Optional[str]
    categoria_nativa: str
    categoria: str  # categoría unificada
    precio: Optional[float]  # EUR
    precio_unidad: Optional[float]  # EUR por unidad de referencia (kg/L/ud)
    unidad: Optional[str]  # kg / L / ud ...
    ean: Optional[str]
    url: Optional[str]
    disponible: bool
    promocion: Optional[str]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_es_price(value: Any) -> Optional[float]:
    """Convierte precios españoles ('1.234,56 €', '1,49', 1.49) a float.

    Devuelve None si no hay un número reconocible.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Deja solo dígitos, puntos y comas
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    if not cleaned:
        return None
    if "," in cleaned:
        # Formato español: el punto es separador de miles, la coma decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_unit(raw: Optional[str]) -> Optional[str]:
    """Normaliza la unidad de referencia a kg / L / ud / m / lavado."""
    if not raw:
        return None
    u = str(raw).strip().lower()
    mapping = {
        "kg": "kg", "kilo": "kg", "kilogramo": "kg", "100g": "kg", "g": "kg",
        "l": "L", "lt": "L", "litro": "L", "100ml": "L", "ml": "L", "cl": "L",
        "ud": "ud", "u": "ud", "unidad": "ud", "unidades": "ud", "uds": "ud",
        "pieza": "ud", "docena": "ud",
        "m": "m", "metro": "m",
        "lavado": "lavado", "dosis": "dosis",
    }
    return mapping.get(u, u)
