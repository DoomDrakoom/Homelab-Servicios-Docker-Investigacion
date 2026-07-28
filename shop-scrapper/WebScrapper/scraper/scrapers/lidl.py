"""Lidl — tienda online lidl.es, sección Alimentación (sin navegador).

Importante: lidl.es solo publica online una parte del surtido; los precios
semanales del supermercado físico viven en la app Lidl Plus (autenticada) y no
se raspan. Su API interna /q/api/search rechaza peticiones fuera del navegador.

Lo que sí es estable:
- Las subcategorías de Alimentación salen del mega-menú de /c/alimentacion/
  (HTML servido): el grupo del menú que contiene el enlace de Alimentación.
- Cada página /h/<slug>/h<id> lleva un payload __NUXT_DATA__ (formato devalue)
  con los productos destacados de la subcategoría: título, marca, precio,
  precio anterior, formato... Se decodifica con scraper.nuxt.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from ..base import BaseScraper
from ..category_map import unify_category
from ..models import Category, Product, normalize_unit, parse_es_price
from ..nuxt import extract_nuxt_data, find_products

log = logging.getLogger("scraper.lidl")

BASE = "https://www.lidl.es"
ROOT_CATEGORY = f"{BASE}/c/alimentacion/s10068374"
ROOT_HREF = "/c/alimentacion/s10068374"

# "1 kg = 2,83 €" / "1 l = 1,99 €" en price.basePrice.text
_BASE_PRICE_RE = re.compile(r"1\s*(kg|l|ud|m)\s*=\s*([\d.,]+)", re.IGNORECASE)


class LidlScraper(BaseScraper):
    chain_id = "lidl"
    chain_name = "Lidl"
    min_delay = 1.5

    def list_categories(self) -> list[Category]:
        html = self.http.get_text(ROOT_CATEGORY)
        soup = BeautifulSoup(html, "html.parser")
        subcats: dict[str, Category] = {}
        for anchor in soup.find_all("a", href=ROOT_HREF):
            # ancestro más cercano con varias entradas /h/ pero acotado (<=20):
            # el grupo del mega-menú de Alimentación, no la navegación completa
            for ancestor in anchor.parents:
                if not hasattr(ancestor, "find_all"):
                    continue
                links = ancestor.find_all("a", href=re.compile(r"^/h/[a-z0-9-]+/h\d+$"))
                if 3 <= len(links) <= 20:
                    for link in links:
                        href = link["href"]
                        cat_id = href.rsplit("/", 1)[-1]
                        name = link.get_text(strip=True) or href.split("/")[2].replace("-", " ")
                        subcats[cat_id] = Category(id=cat_id, name=name,
                                                   parent="Alimentación", url=BASE + href)
                    break
                if len(links) > 20:
                    break  # ya estamos en la navegación completa; probar otro anchor
            if subcats:
                break
        if not subcats:
            log.warning("[lidl] no se encontraron subcategorias en el menu; se usa la raiz")
            return [Category(id="s10068374", name="Alimentación", url=ROOT_CATEGORY)]
        return list(subcats.values())

    def list_products(self, category: Category) -> list[dict]:
        html = self.http.get_text(category.url)
        data = extract_nuxt_data(html)
        if not data:
            log.warning("[lidl] sin __NUXT_DATA__ en %s", category.url)
            return []
        return find_products(data)

    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        name = (raw.get("fullTitle") or raw.get("title") or "").strip()
        if not name:
            return None
        price_info = raw.get("price") or {}
        price = price_info.get("price")
        old_price = price_info.get("oldPrice")
        packaging = ((price_info.get("packaging") or {}).get("text") or "").strip()
        if packaging:
            name = f"{name} ({packaging})"

        promo = None
        if old_price and price and old_price > price:
            promo = f"Rebajado (antes {old_price} EUR)"

        ppu = unit = None
        base_price_text = ((price_info.get("basePrice") or {}).get("text") or "")
        match = _BASE_PRICE_RE.search(base_price_text)
        if match:
            unit = match.group(1)
            ppu = parse_es_price(match.group(2))

        brand = ((raw.get("brand") or {}).get("name") or "").strip() or None
        path = raw.get("canonicalPath") or raw.get("canonicalUrl")
        return Product(
            cadena=self.chain_name,
            nombre=name,
            marca=brand,
            categoria_nativa=category.full_name,
            categoria=unify_category(category.name),
            precio=float(price) if price is not None else None,
            precio_unidad=ppu,
            unidad=normalize_unit(unit),
            ean=None,  # el payload trae el IAN interno de Lidl, no el EAN
            url=BASE + path if path and path.startswith("/") else path,
            disponible=not raw.get("preventSelling", False),
            promocion=promo,
        )
