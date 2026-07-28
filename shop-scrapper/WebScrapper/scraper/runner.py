"""Orquestación de un trabajo de scraping multi-cadena + exportación a Excel."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from .base import ScraperUnavailable
from .excel_export import export_to_excel
from .models import Product
from .registry import get_scraper

log = logging.getLogger("scraper.runner")

# job_progress(cadena, evento, payload) — evento: "start"|"category"|"done"|"error"
JobProgress = Callable[[str, str, dict], None]


def run_scrape_job(
    chains: list[str],
    categories: Optional[dict[str, list[str]]] = None,
    progress: Optional[JobProgress] = None,
    out_dir: str | Path = "data/exports",
    filename: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    """Raspa las cadenas indicadas y genera el Excel.

    categories: filtro opcional {chain_id: [category_id, ...]}.
    Devuelve {"file": ruta, "products": n, "chains": {chain: n|error}}.
    """
    categories = categories or {}
    all_products: list[Product] = []
    summary: dict[str, object] = {}

    def notify(chain: str, event: str, payload: dict) -> None:
        if progress:
            progress(chain, event, payload)

    for chain in chains:
        notify(chain, "start", {})
        scraper = None
        try:
            scraper = get_scraper(chain, use_cache=use_cache)
            products = scraper.scrape(
                category_ids=categories.get(chain),
                progress=lambda idx, total, name, count: notify(
                    chain, "category",
                    {"index": idx, "total": total, "category": name, "products": count},
                ),
            )
        except ScraperUnavailable as exc:
            log.error("[%s] no disponible: %s", chain, exc)
            summary[chain] = f"no disponible: {exc}"
            notify(chain, "error", {"message": str(exc)})
            continue
        except Exception as exc:
            log.exception("[%s] fallo inesperado", chain)
            summary[chain] = f"error: {exc}"
            notify(chain, "error", {"message": str(exc)})
            continue
        finally:
            browser = getattr(scraper, "browser", None)
            if browser is not None:
                browser.close()
        all_products.extend(products)
        summary[chain] = len(products)
        notify(chain, "done", {"products": len(products)})

    filename = filename or f"productos_{date.today().strftime('%Y%m%d')}.xlsx"
    path = export_to_excel(all_products, out_dir=out_dir, filename=filename)
    log.info("Excel generado: %s (%d productos)", path, len(all_products))
    return {"file": str(path), "products": len(all_products), "chains": summary}
