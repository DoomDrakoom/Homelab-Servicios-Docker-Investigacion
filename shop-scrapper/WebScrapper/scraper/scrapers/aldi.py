"""Aldi — catálogo público de aldi.es (renderizado con JS, requiere Playwright).

aldi.es no tiene tienda online: publica dos cosas raspables,
1. "Ofertas" (/ofertas.html): tarjetas con marca, nombre y precio.
2. "Surtido" (sitemap de productos, ~360 fichas /producto/<slug>-<id>.html): cada
   ficha muestra el precio solo tras renderizar con navegador, así que esta
   categoría es LENTA (una navegación por producto, ~15-25 min con el delay por
   defecto). El resto del surtido de tienda física no se publica en la web.

No hay API JSON accesible sin navegador (el contenido llega vía Magnolia CMS
tras el consentimiento de cookies).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..base import BaseScraper
from ..browser import BrowserSession
from ..category_map import unify_category
from ..models import Category, Product, normalize_unit, parse_es_price

log = logging.getLogger("scraper.aldi")

BASE = "https://www.aldi.es"
SITEMAP = f"{BASE}/sitemaps/.aldi-nord-sitemap-products.xml"

# Tarjetas de /ofertas.html: el precio aparece como línea propia "14,99" (sin €)
_OFFERS_JS = """
() => {
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href*="/producto/"]')) {
    const href = a.href.split('#')[0];
    if (seen.has(href)) continue;
    const tile = a.closest('article, li, div');
    const text = tile ? (tile.innerText || '') : '';
    const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
    const priceIdx = lines.findIndex(l => /^\\d+[.,]\\d{2}$/.test(l));
    if (priceIdx < 0) continue;
    const brand = lines.find(l => /\\u00ae$/.test(l)) || null;
    const name = lines.find(l => l !== brand && !/^\\d+[.,]\\d{2}$/.test(l) && l.length > 3) || '';
    if (!name) continue;
    seen.add(href);
    out.push({
      name,
      brand: brand ? brand.replace(/\\u00ae$/, '').trim() : null,
      price_text: lines[priceIdx],
      unit_text: lines[priceIdx + 1] || null,
      url: href,
    });
  }
  return out;
}
"""

# Ficha de producto individual (tras render): precio y precio/unidad del texto
_PRODUCT_JS = """
() => {
  const h1 = document.querySelector('h1');
  const text = document.body.innerText || '';
  const prices = text.match(/\\d+,\\d{2}/g) || [];
  const ppu = text.match(/(\\d+,\\d{2})\\s*\\u20ac?\\s*(?:\\/|por)\\s*(kg|l|litro|ud|100\\s?g|100\\s?ml)/i);
  return {
    name: h1 ? h1.innerText.trim() : '',
    price_text: prices.length ? prices[0] : null,
    ppu_text: ppu ? ppu[1] : null,
    ppu_unit: ppu ? ppu[2] : null,
    url: location.href,
  };
}
"""


class AldiScraper(BaseScraper):
    chain_id = "aldi"
    chain_name = "Aldi"
    min_delay = 2.0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.browser = BrowserSession(min_delay=self.min_delay)

    def list_categories(self) -> list[Category]:
        return [
            Category(id="ofertas", name="Ofertas de la semana", url=f"{BASE}/ofertas.html"),
            Category(id="surtido", name="Surtido (fichas de producto, lento)", url=SITEMAP),
        ]

    def _product_urls(self) -> list[str]:
        xml = self.http.get_text(SITEMAP)
        return re.findall(r"<loc>(https://www\.aldi\.es/producto/[^<]+)</loc>", xml)

    def list_products(self, category: Category) -> list[dict]:
        if category.id == "ofertas":
            items = self.browser.extract(category.url, _OFFERS_JS,
                                         wait_selector="a[href*='/producto/']", scroll_steps=8)
            for item in items:
                item["_source"] = "ofertas"
            return items
        urls = self._product_urls()
        log.info("[aldi] surtido: %d fichas de producto (esto tarda)", len(urls))
        items = []
        for n, url in enumerate(urls, start=1):
            try:
                raw = self.browser.extract(url, _PRODUCT_JS, wait_selector="h1", scroll_steps=1)
            except Exception:
                log.exception("[aldi] fallo en %s", url)
                continue
            if raw.get("name") and raw.get("price_text"):
                raw["_source"] = "surtido"
                items.append(raw)
            if n % 25 == 0:
                log.info("[aldi] surtido %d/%d fichas", n, len(urls))
        return items

    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        name = re.sub(r"\s+", " ", raw.get("name") or "").strip()
        if not name:
            return None
        unit = raw.get("ppu_unit")
        if not unit and raw.get("unit_text"):
            unit_text = raw["unit_text"].lower()
            unit = "ud" if "unidad" in unit_text else None
        return Product(
            cadena=self.chain_name,
            nombre=name,
            marca=raw.get("brand"),
            categoria_nativa=category.full_name,
            # Aldi no publica taxonomía: se infiere de las palabras del nombre
            categoria=unify_category(name),
            precio=parse_es_price(raw.get("price_text")),
            precio_unidad=parse_es_price(raw.get("ppu_text")),
            unidad=normalize_unit(unit),
            ean=None,
            url=raw.get("url"),
            disponible=True,
            promocion="Oferta semanal" if raw.get("_source") == "ofertas" else None,
        )
