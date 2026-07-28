"""Decodificador del payload __NUXT_DATA__ (formato "devalue" de Nuxt 3).

El payload es un array JSON plano donde cada valor referencia a otros por índice:
- dict: {clave: índice_del_valor}
- list: [índice, índice, ...]
- wrappers: ["Ref", índice], ["Reactive", índice], ["Date", índice]...
- primitivos: literales

resolve() reconstruye el objeto anidado a partir de un índice.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

_NUXT_DATA_RE = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)
_WRAPPERS = {"Ref", "ShallowRef", "Reactive", "ShallowReactive", "EmptyRef", "Date"}


def extract_nuxt_data(html: str) -> Optional[list]:
    match = _NUXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def resolve(data: list, index: int, max_depth: int = 12, _depth: int = 0) -> Any:
    """Reconstruye el valor en `index` siguiendo referencias (con tope de profundidad)."""
    if _depth > max_depth or not isinstance(index, int) or not 0 <= index < len(data):
        return None
    value = data[index]
    if isinstance(value, dict):
        return {k: resolve(data, i, max_depth, _depth + 1)
                for k, i in value.items() if isinstance(i, int)}
    if isinstance(value, list):
        if (len(value) == 2 and isinstance(value[0], str)
                and value[0] in _WRAPPERS and isinstance(value[1], int)):
            return resolve(data, value[1], max_depth, _depth + 1)
        return [resolve(data, i, max_depth, _depth + 1)
                for i in value if isinstance(i, int)]
    return value


def find_products(data: list, required_keys: tuple[str, ...] = ("erpNumber", "price")) -> list[dict]:
    """Devuelve, resueltos, los dicts del payload que parecen productos."""
    products = []
    for i, value in enumerate(data):
        if isinstance(value, dict) and all(k in value for k in required_keys):
            resolved = resolve(data, i)
            if isinstance(resolved, dict):
                products.append(resolved)
    return products
