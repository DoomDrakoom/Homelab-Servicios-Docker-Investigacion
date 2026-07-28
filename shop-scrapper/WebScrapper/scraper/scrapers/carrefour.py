"""Carrefour — páginas de categoría del supermercado con estado embebido.

- El menú de categorías sí es una API JSON pública:
  https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu
- Las páginas /supermercado/<slug>/cat<ID>/c llevan window.__INITIAL_STATE__ con
  productCardList.results.items y paginación por ?offset=N (24 por página).
- El array window["impressions"] de analítica incluye el EAN, que se cruza por id.

Carrefour usa protección anti-bot (Akamai) que valida la huella TLS del cliente:
requests puro recibe 403, así que las peticiones se hacen con curl_cffi
imitando a Chrome (HttpClient(impersonate="chrome")).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from ..base import BaseScraper
from ..http import HttpClient
from ..category_map import unify_category
from ..models import Category, Product, normalize_unit, parse_es_price

log = logging.getLogger("scraper.carrefour")

BASE = "https://www.carrefour.es"
MENU_URL = f"{BASE}/cloud-api/categories-api/v1/categories/menu"
PAGE_SIZE = 24
MAX_PRODUCTS_PER_CATEGORY = 2000  # cortafuegos por si la paginación se descontrola

_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*")
_IMPRESSIONS_RE = re.compile(r'window\["impressions"\]\s*=\s*')


def _extract_json_after(pattern: re.Pattern, html: str):
    match = pattern.search(html)
    if not match:
        return None
    try:
        return json.JSONDecoder().raw_decode(html[match.end():])[0]
    except (json.JSONDecodeError, ValueError):
        return None


class CarrefourScraper(BaseScraper):
    chain_id = "carrefour"
    chain_name = "Carrefour"
    min_delay = 2.0

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("http", HttpClient(min_delay=self.min_delay, impersonate="chrome"))
        super().__init__(**kwargs)

    def list_categories(self) -> list[Category]:
        menu = self.http.get_json(MENU_URL)
        categories: list[Category] = []
        for entry in menu.get("menu", []):
            if entry.get("analytics", {}).get("data_bu") != "food":
                continue
            for level1 in entry.get("childs") or []:
                if not level1.get("food", True) and not (level1.get("childs") or []):
                    continue
                children = level1.get("childs") or []
                if not children:
                    categories.append(Category(
                        id=level1["id"], name=level1["name"],
                        url=BASE + level1["url_rel"],
                    ))
                for level2 in children:
                    url_rel = level2.get("url_rel")
                    if not url_rel or not url_rel.endswith("/c"):
                        continue
                    categories.append(Category(
                        id=level2["id"], name=level2["name"], parent=level1["name"],
                        url=BASE + url_rel,
                    ))
            break  # solo la entrada "Supermercado"
        return categories

    def _fetch_grid(self, category: Category, offset: int):
        url = category.url if offset == 0 else f"{category.url}?offset={offset}"
        html = self.http.get_text(url)
        state = _extract_json_after(_STATE_RE, html)
        if not state:
            log.warning("[carrefour] sin __INITIAL_STATE__ en %s", url)
            return [], 0, {}
        results = ((state.get("productCardList") or {}).get("results") or {})
        items = results.get("items") or []
        pagination = results.get("pagination") or {}
        total = pagination.get("total_results") or 0
        # EANs desde el array de impresiones de analítica (item_id -> ean13)
        eans: dict[str, str] = {}
        for imp in _extract_json_after(_IMPRESSIONS_RE, html) or []:
            if imp.get("item_id") and imp.get("item_ean"):
                eans[str(imp["item_id"])] = str(imp["item_ean"])
        return items, total, eans

    def list_products(self, category: Category) -> list[dict]:
        items, total, eans = self._fetch_grid(category, 0)
        collected = list(items)
        offset = PAGE_SIZE
        limit = min(total, MAX_PRODUCTS_PER_CATEGORY)
        while offset < limit and items:
            items, _, page_eans = self._fetch_grid(category, offset)
            eans.update(page_eans)
            collected.extend(items)
            offset += PAGE_SIZE
        for raw in collected:
            sku = str(raw.get("sku_id") or "")
            # sku_id = item_id + 4 dígitos de variante (p. ej. 0358340000 -> 035834)
            raw["_ean"] = eans.get(sku[:-4]) if len(sku) > 4 else None
        return collected

    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        name = (raw.get("name") or "").strip()
        if not name:
            return None
        promo = None
        promotions = ((raw.get("badge_map") or {}).get("promotions") or [])
        if promotions:
            promo = "; ".join(p.get("name", "") for p in promotions if p.get("name")) or None
        elif raw.get("badge"):
            promo = raw["badge"].get("name")
        brand = (raw.get("brand") or "").strip()
        if brand.upper() in ("MARCA NACIONAL SIN MARCA", "SIN MARCA"):
            brand = ""
        url = raw.get("url")
        return Product(
            cadena=self.chain_name,
            nombre=name,
            marca=brand.title() or None,
            categoria_nativa=category.full_name,
            categoria=unify_category(category.parent, category.name),
            precio=parse_es_price(raw.get("price")),
            precio_unidad=parse_es_price(raw.get("price_per_unit")),
            unidad=normalize_unit(raw.get("measure_unit")),
            ean=raw.get("_ean"),
            url=BASE + url if url and url.startswith("/") else url,
            disponible=(raw.get("units_in_stock") or 0) > 0,
            promocion=promo,
        )
