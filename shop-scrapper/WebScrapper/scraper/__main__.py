"""CLI: python -m scraper --chains mercadona,dia [--categories id1,id2] [--no-cache]"""
from __future__ import annotations

import argparse
import logging

from .registry import SCRAPERS
from .runner import run_scrape_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper de supermercados -> Excel")
    parser.add_argument("--chains", required=True,
                        help=f"cadenas separadas por comas ({','.join(SCRAPERS)})")
    parser.add_argument("--categories", default=None,
                        help="ids de categoría separados por comas (aplica a todas las cadenas pedidas)")
    parser.add_argument("--no-cache", action="store_true", help="ignora la caché en disco")
    parser.add_argument("--out", default="data/exports", help="directorio de salida")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]
    categories = None
    if args.categories:
        ids = [c.strip() for c in args.categories.split(",") if c.strip()]
        categories = {chain: ids for chain in chains}
    result = run_scrape_job(chains, categories=categories, out_dir=args.out,
                            use_cache=not args.no_cache)
    print(f"\nExcel: {result['file']}")
    print(f"Productos: {result['products']}")
    for chain, info in result["chains"].items():
        print(f"  {chain}: {info}")


if __name__ == "__main__":
    main()
