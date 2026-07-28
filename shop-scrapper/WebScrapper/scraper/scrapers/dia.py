"""Dia — páginas de categoría renderizadas en servidor con JSON embebido.

Las páginas /​<cat>/<subcat>/c/<ID> incluyen un <script id="vike_pageContext"> con
INITIAL_STATE.l2.plp_items (productos) y la paginación. Las categorías se
descubren desde el sitemap. La paginación usa /pag-N/; el robots.txt de dia.es
solo permite hasta pag-5 (100 productos por subcategoría), se registra un aviso
si una categoría tiene más páginas.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from ..base import BaseScraper
from ..category_map import unify_category
from ..models import Category, Product, normalize_unit, parse_es_price

log = logging.getLogger("scraper.dia")

BASE = "https://www.dia.es"
MAX_PAGES = 5  # robots.txt: Allow */pag-1..5, Disallow */pag-*
_CONTEXT_RE = re.compile(
    r'<script id="vike_pageContext" type="application/json">(.*?)</script>', re.S
)


def _slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").capitalize()


class DiaScraper(BaseScraper):
    chain_id = "dia"
    chain_name = "Dia"
    min_delay = 1.5

    def list_categories(self) -> list[Category]:
        xml = self.http.get_text(f"{BASE}/sitemap.xml")
        seen: dict[str, Category] = {}
        for match in re.finditer(r"<loc>(https://www\.dia\.es/([^<]+)/c/(L\d+))</loc>", xml):
            url, path, cat_id = match.groups()
            parts = path.split("/")
            level1 = _slug_to_name(parts[0])
            level2 = _slug_to_name(parts[1]) if len(parts) > 1 else level1
            if cat_id not in seen:
                seen[cat_id] = Category(id=cat_id, name=level2, parent=level1, url=url)
        return sorted(seen.values(), key=lambda c: (c.parent or "", c.name))

    def _fetch_page_state(self, url: str) -> Optional[dict]:
        html = self.http.get_text(url)
        match = _CONTEXT_RE.search(html)
        if not match:
            log.warning("[dia] sin vike_pageContext en %s", url)
            return None
        try:
            return json.loads(match.group(1)).get("INITIAL_STATE") or {}
        except json.JSONDecodeError:
            log.warning("[dia] JSON invalido en %s", url)
            return None

    def list_products(self, category: Category) -> list[dict]:
        state = self._fetch_page_state(category.url)
        if not state:
            return []
        items = list((state.get("l2") or {}).get("plp_items") or [])
        pagination = state.get("pagination") or {}
        total_pages = (pagination.get("pagination") or {}).get("total_pages") or 1
        if total_pages > MAX_PAGES:
            log.warning("[dia] '%s' tiene %d paginas; robots.txt solo permite %d",
                        category.name, total_pages, MAX_PAGES)
        base_path = urlparse(category.url).path  # /<l1>/<l2>/c/<ID>
        for page in range(2, min(total_pages, MAX_PAGES) + 1):
            paged_path = base_path.replace("/c/", f"/pag-{page}/c/")
            state = self._fetch_page_state(f"{BASE}{paged_path}")
            if state:
                items.extend((state.get("l2") or {}).get("plp_items") or [])
        return items

    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        name = (raw.get("display_name") or "").strip()
        if not name:
            return None
        prices = raw.get("prices") or {}
        promo = None
        if prices.get("is_promo_price") or prices.get("is_club_price"):
            strike = prices.get("strikethrough_price")
            label = "Precio Club Dia" if prices.get("is_club_price") else "Promoción"
            promo = f"{label} (antes {strike} EUR)" if strike else label
        elif prices.get("discount_percentage"):
            promo = f"-{prices['discount_percentage']}%"
        url = raw.get("url")
        return Product(
            cadena=self.chain_name,
            nombre=name,
            marca=raw.get("brand") or None,
            categoria_nativa=category.full_name,
            categoria=unify_category(category.parent, category.name),
            precio=parse_es_price(prices.get("price")),
            precio_unidad=parse_es_price(prices.get("price_per_unit")),
            unidad=normalize_unit(prices.get("measure_unit")),
            ean=None,
            url=f"{BASE}{url}" if url else None,
            disponible=(raw.get("units_in_stock") or 0) > 0,
            promocion=promo,
        )
