"""Clase base de todos los scrapers (patrón adapter).

Para añadir una cadena nueva:
1. Crea scraper/scrapers/<cadena>.py con una clase que herede de BaseScraper.
2. Implementa list_categories(), list_products(category) y parse_product(raw, category).
3. Regístrala en scraper/registry.py.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .cache import RawCache
from .http import HttpClient
from .models import Category, Product

log = logging.getLogger("scraper")

# progreso: (categoria_actual_idx, total_categorias, nombre_categoria, productos_acumulados)
ProgressCallback = Callable[[int, int, str, int], None]


class ScraperUnavailable(Exception):
    """El scraper no puede ejecutarse en este entorno (p. ej. falta Playwright)."""


class BaseScraper(ABC):
    chain_id: str = ""  # identificador corto, p. ej. "mercadona"
    chain_name: str = ""  # nombre visible, p. ej. "Mercadona"
    min_delay: float = 1.0  # segundos entre peticiones al dominio

    def __init__(self, http: Optional[HttpClient] = None, cache: Optional[RawCache] = None,
                 use_cache: bool = True) -> None:
        self.http = http or HttpClient(min_delay=self.min_delay)
        self.cache = cache or RawCache(self.chain_id)
        self.use_cache = use_cache

    # ------------------------------------------------------------------ API
    @abstractmethod
    def list_categories(self) -> list[Category]:
        """Devuelve las categorías nativas raspables de la cadena."""

    @abstractmethod
    def list_products(self, category: Category) -> list[dict]:
        """Devuelve los productos crudos (dicts tal cual los da la web/API)."""

    @abstractmethod
    def parse_product(self, raw: dict, category: Category) -> Optional[Product]:
        """Convierte un producto crudo en Product. None para descartarlo."""

    # ------------------------------------------------------------- orquesta
    def scrape(
        self,
        category_ids: Optional[list[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> list[Product]:
        """Raspa la cadena completa (o las categorías indicadas).

        Usa la caché en disco: las categorías ya descargadas recientemente no se
        vuelven a pedir, de modo que un scrape interrumpido es reanudable.
        """
        categories = self.list_categories()
        if category_ids:
            wanted = {str(c) for c in category_ids}
            categories = [c for c in categories if str(c.id) in wanted]
        total = len(categories)
        products: list[Product] = []
        seen_urls: set[str] = set()
        for idx, category in enumerate(categories, start=1):
            raw_items = self.cache.get(category.id) if self.use_cache else None
            if raw_items is None:
                try:
                    raw_items = self.list_products(category)
                except Exception:
                    log.exception("[%s] fallo en la categoria '%s'", self.chain_id, category.name)
                    raw_items = []
                else:
                    self.cache.set(category.id, raw_items)
            else:
                log.info("[%s] categoria '%s' recuperada de cache (%d items)",
                         self.chain_id, category.name, len(raw_items))
            for raw in raw_items:
                try:
                    product = self.parse_product(raw, category)
                except Exception:
                    log.exception("[%s] error parseando producto en '%s'", self.chain_id, category.name)
                    continue
                if product is None:
                    continue
                key = product.url or f"{product.nombre}|{product.categoria_nativa}"
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                products.append(product)
            log.info("[%s] %d/%d '%s': %d productos acumulados",
                     self.chain_id, idx, total, category.name, len(products))
            if progress:
                progress(idx, total, category.name, len(products))
        return products
