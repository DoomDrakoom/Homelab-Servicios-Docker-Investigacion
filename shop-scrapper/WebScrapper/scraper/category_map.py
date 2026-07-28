"""Normalización de la taxonomía de cada cadena a un conjunto unificado de categorías.

La categoría nativa se conserva siempre en el producto; aquí solo se decide a qué
categoría unificada pertenece, mediante reglas de palabras clave insensibles a
mayúsculas y acentos. Para añadir una cadena nueva normalmente no hace falta tocar
nada: las reglas operan sobre el texto de la categoría nativa.
"""
from __future__ import annotations

import re
import unicodedata

UNIFIED_CATEGORIES = [
    "Frutas y Verduras",
    "Carne",
    "Pescado y Marisco",
    "Charcutería y Quesos",
    "Panadería y Repostería",
    "Lácteos y Huevos",
    "Despensa",
    "Desayuno y Dulces",
    "Aperitivos",
    "Platos Preparados",
    "Congelados",
    "Bebidas",
    "Bebidas Alcohólicas",
    "Bebé e Infantil",
    "Mascotas",
    "Higiene y Belleza",
    "Limpieza y Hogar",
    "Otros",
]

# Reglas evaluadas en orden: la primera palabra clave que aparezca en la categoría
# nativa (nivel 1 + nivel 2 concatenados) decide la categoría unificada.
_RULES: list[tuple[str, list[str]]] = [
    ("Bebidas Alcohólicas", [
        "cerveza", "vino", "licor", "alcohol", "cava", "champagne", "sidra",
        "ginebra", "whisky", "ron", "vodka", "vermut", "bodega",
    ]),
    ("Congelados", ["congelado", "helado", "hielo"]),
    # antes que Charcutería: "Lácteos, Queso y Huevos" debe caer aquí pese al "queso"
    ("Lácteos y Huevos", ["leche", "lacteo", "huevo", "yogur", "mantequilla", "nata"]),
    ("Charcutería y Quesos", ["charcuteria", "queso", "embutido", "jamon", "fiambre", "salchichon", "chorizo"]),
    ("Pescado y Marisco", ["pescado", "marisco", "pescaderia", "sushi", "ahumado"]),
    ("Carne", ["carne", "carniceria", "pollo", "cerdo", "ternera", "cordero", "pavo", "conejo", "hamburguesa"]),
    ("Frutas y Verduras", ["fruta", "verdura", "hortaliza", "ensalada", "lechuga", "patata", "seta", "granel"]),
    ("Panadería y Repostería", ["pan", "panaderia", "bolleria", "pasteleria", "reposteria", "harina", "levadura", "tarta", "horno"]),
    ("Lácteos y Huevos", ["batido", "postre"]),
    ("Desayuno y Dulces", [
        "cereal", "galleta", "mermelada", "cacao", "chocolate", "golosina",
        "caramelo", "azucar", "miel", "desayuno", "dulce", "turron", "cafe", "infusion", "te",
    ]),
    ("Aperitivos", ["aperitivo", "snack", "patatas fritas", "fruto seco", "aceituna", "encurtido", "palomita"]),
    ("Platos Preparados", ["preparado", "listo para", "pizza", "cocina internacional", "comida internacional"]),
    ("Bebé e Infantil", ["bebe", "infantil", "panal", "papilla"]),
    ("Mascotas", ["mascota", "perro", "gato", "animal"]),
    ("Higiene y Belleza", [
        "higiene", "belleza", "cuidado", "perfume", "cosmetic", "champu", "gel",
        "desodorante", "dental", "afeitado", "depilacion", "parafarmacia", "salud", "maquillaje",
    ]),
    ("Limpieza y Hogar", [
        "limpieza", "hogar", "detergente", "lavavajillas", "papel", "celulosa",
        "bazar", "menaje", "drogueria", "insecticida", "bolsa", "utensilio", "cocina y",
    ]),
    ("Bebidas", [
        "agua", "refresco", "zumo", "bebida", "isotonic", "energetic", "smoothie", "gaseosa", "cola",
    ]),
    ("Despensa", [
        "aceite", "vinagre", "sal", "especia", "salsa", "arroz", "pasta", "legumbre",
        "conserva", "caldo", "sopa", "despensa", "tomate", "alimentacion", "huerta",
    ]),
]


def _fold(text: str) -> str:
    """minúsculas + sin acentos para comparar."""
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _compile(keyword: str) -> re.Pattern:
    # Límite de palabra al inicio siempre; las palabras muy cortas exigen palabra
    # completa para evitar falsos positivos ("te" en "aceiTE De", "sal" en "SALud").
    suffix = r"\b" if len(keyword) <= 3 else ""
    return re.compile(r"\b" + re.escape(keyword) + suffix)


_COMPILED_RULES: list[tuple[str, list[re.Pattern]]] = [
    (unified, [_compile(kw) for kw in keywords]) for unified, keywords in _RULES
]


def unify_category(*native_names: str | None) -> str:
    """Mapea una o varias categorías nativas (nivel 1, nivel 2...) a la unificada."""
    haystack = _fold(" ".join(n for n in native_names if n))
    if not haystack.strip():
        return "Otros"
    for unified, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(haystack):
                return unified
    return "Otros"
