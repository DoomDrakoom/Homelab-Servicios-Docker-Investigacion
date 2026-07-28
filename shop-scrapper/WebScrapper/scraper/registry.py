"""Registro de cadenas disponibles.

Para dar de alta una cadena nueva basta con importar su clase y añadirla a SCRAPERS.
"""
from __future__ import annotations

from .base import BaseScraper
from .scrapers.mercadona import MercadonaScraper
from .scrapers.dia import DiaScraper
from .scrapers.carrefour import CarrefourScraper
from .scrapers.aldi import AldiScraper
from .scrapers.lidl import LidlScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    MercadonaScraper.chain_id: MercadonaScraper,
    DiaScraper.chain_id: DiaScraper,
    CarrefourScraper.chain_id: CarrefourScraper,
    AldiScraper.chain_id: AldiScraper,
    LidlScraper.chain_id: LidlScraper,
}


def get_scraper(chain_id: str, **kwargs) -> BaseScraper:
    try:
        cls = SCRAPERS[chain_id]
    except KeyError:
        raise KeyError(f"Cadena desconocida: {chain_id!r}. Disponibles: {sorted(SCRAPERS)}")
    return cls(**kwargs)


def available_chains() -> list[dict]:
    return [{"id": cls.chain_id, "name": cls.chain_name} for cls in SCRAPERS.values()]
