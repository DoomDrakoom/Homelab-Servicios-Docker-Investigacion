"""Mercadona — API JSON pública de la tienda online.

Endpoints:
- https://tienda.mercadona.es/api/categories/            -> árbol de categorías (2 niveles)
- https://tienda.mercadona.es/api/categories/{id}/       -> secciones con productos

Los precios dependen del almacén (parámetro opcional 'wh'); sin él, la API usa el
almacén por defecto. Nota: el robots.txt de Mercadona excluye /api para crawlers
genéricos; este scraper hace un volumen bajo de peticiones (una por subcategoría,
~160 en total) con delay configurable.
"""
from __future__ import annotations

from typing import Optional

from ..base import BaseScraper
from ..category_map import unify_category
from ..models import Category, Product, normalize_unit, parse_es_price

BASE = "https://tienda.mercadona.es/api"

# Marcas propias habituales de Mercadona, para inferir la marca desde el nombre
_OWN_BRANDS = ("Hacendado", "Deliplus", "Bosque Verde", "Compy", "Steinburg", "Belcolade")


class MercadonaScraper(BaseScraper):
    chain_id = "mercadona"
    chain_name = "Mercadona"
    min_delay = 1.0

    def __init__(self, warehouse: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.warehouse = warehouse  # código de almacén, p. ej. "mad1"

    def _params(self) -> dict:
        params = {"lang": "es"}
        if self.warehouse:
            params["wh"] = self.warehouse
        return params

    def list_categories(self) -> list[Category]:
        data = self.http.get_json(f"{BASE}/categories/", params=self._params())
        categories = []
        for level1 in data.get("results", []):
            for level2 in level1.get("categories", []):
                categories.append(
                    Category(
                        id=str(level2["id"]),
                        name=level2["name"],
                        parent=level1["name"],
                        url=f"{BASE}/categories/{level2['id']}/",
                    )
                )
        return categories

    def list_products(self, category: Category) -> list[dict]:
        data = self.http.get_json(f"{BASE}/categories/{category.id}/", params=self._params())
        items = []
        for section in data.get("categories", []):
            for product in section.get("products", []):
                product["_section"] = section.get("name")
                items.append(product)
        return items

    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        if not raw.get("published", True):
            return None
        price_info = raw.get("price_instructions") or {}
        name = raw.get("display_name") or ""
        packaging = raw.get("packaging")
        if packaging:
            name = f"{name} ({packaging})"
        brand = next((b for b in _OWN_BRANDS if b.lower() in name.lower()), None)
        promo = None
        if price_info.get("price_decreased"):
            previous = price_info.get("previous_unit_price")
            promo = f"Precio rebajado (antes {previous} EUR)" if previous else "Precio rebajado"
        native = f"{category.full_name}" + (f" > {raw['_section']}" if raw.get("_section") else "")
        return Product(
            cadena=self.chain_name,
            nombre=name.strip(),
            marca=brand,
            categoria_nativa=native,
            categoria=unify_category(category.parent, category.name, raw.get("_section")),
            precio=parse_es_price(price_info.get("unit_price")),
            precio_unidad=parse_es_price(price_info.get("reference_price")),
            unidad=normalize_unit(price_info.get("reference_format")),
            ean=None,  # la API de listado no expone EAN
            url=raw.get("share_url"),
            disponible=raw.get("unavailable_from") is None,
            promocion=promo,
        )
