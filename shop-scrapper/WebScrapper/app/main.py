"""API FastAPI: lanzar scrapes, seguir progreso vía SSE y descargar el Excel."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from scraper.base import ScraperUnavailable
from scraper.registry import SCRAPERS, available_chains, get_scraper
from .jobs import manager

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Supermercados Scraper", version="1.0")

STATIC_DIR = Path(__file__).parent / "static"
_categories_cache: dict[str, tuple[float, list]] = {}
CATEGORIES_TTL = 3600


class ScrapeRequest(BaseModel):
    chains: list[str] = Field(min_length=1)
    categories: Optional[dict[str, list[str]]] = None  # filtro opcional por cadena
    use_cache: bool = True


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/chains")
def chains() -> list[dict]:
    return available_chains()


@app.get("/api/chains/{chain_id}/categories")
async def chain_categories(chain_id: str) -> list[dict]:
    if chain_id not in SCRAPERS:
        raise HTTPException(404, f"Cadena desconocida: {chain_id}")
    cached = _categories_cache.get(chain_id)
    if cached and time.time() - cached[0] < CATEGORIES_TTL:
        return cached[1]

    def fetch() -> list[dict]:
        scraper = get_scraper(chain_id)
        try:
            return [
                {"id": str(c.id), "name": c.full_name}
                for c in scraper.list_categories()
            ]
        finally:
            browser = getattr(scraper, "browser", None)
            if browser is not None:
                browser.close()

    try:
        result = await asyncio.to_thread(fetch)
    except ScraperUnavailable as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        logging.getLogger("app").exception("Error listando categorias de %s", chain_id)
        raise HTTPException(502, f"No se pudieron obtener las categorías: {exc}")
    _categories_cache[chain_id] = (time.time(), result)
    return result


@app.post("/api/scrape")
def scrape(req: ScrapeRequest) -> dict:
    unknown = [c for c in req.chains if c not in SCRAPERS]
    if unknown:
        raise HTTPException(400, f"Cadenas desconocidas: {unknown}")
    job_id = manager.start(req.chains, categories=req.categories, use_cache=req.use_cache)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str) -> dict:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    return job


@app.get("/api/events/{job_id}")
async def events(job_id: str) -> StreamingResponse:
    """Progreso en vivo vía Server-Sent Events."""
    if not manager.get(job_id):
        raise HTTPException(404, "Job no encontrado")

    async def stream():
        last_payload = None
        while True:
            job = manager.get(job_id)
            payload = json.dumps(job, ensure_ascii=False)
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job["status"] in ("done", "error"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/download/{job_id}")
def download(job_id: str) -> FileResponse:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    if job["status"] != "done" or not job["file"]:
        raise HTTPException(409, "El job aún no ha terminado")
    path = Path(job["file"])
    if not path.exists():
        raise HTTPException(410, "El fichero ya no existe")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/jobs")
def jobs() -> list[dict]:
    return manager.history()
