"""Gestor de trabajos de scraping en segundo plano con historial persistente."""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scraper.runner import run_scrape_job

log = logging.getLogger("app.jobs")

HISTORY_FILE = Path("data/jobs.json")
MAX_HISTORY = 50


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load_history()

    # ------------------------------------------------------------ historial
    def _load_history(self) -> None:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, encoding="utf-8") as fh:
                    for job in json.load(fh):
                        self._jobs[job["id"]] = job
            except (json.JSONDecodeError, OSError):
                log.warning("Historial de jobs corrupto; se ignora")

    def _save_history(self) -> None:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        jobs = sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(jobs[:MAX_HISTORY], fh, ensure_ascii=False, indent=1)

    # -------------------------------------------------------------- trabajos
    def start(self, chains: list[str], categories: Optional[dict[str, list[str]]] = None,
              use_cache: bool = True) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "created_at": _now(),
            "status": "running",
            "chains": chains,
            "progress": {c: {"state": "pending", "index": 0, "total": 0,
                             "category": "", "products": 0} for c in chains},
            "percent": 0,
            "file": None,
            "products": None,
            "error": None,
            "finished_at": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job_id, chains, categories, use_cache),
                                  daemon=True, name=f"job-{job_id}")
        thread.start()
        return job_id

    def _update_percent(self, job: dict) -> None:
        chains = job["chains"]
        if not chains:
            job["percent"] = 100
            return
        share = 100.0 / len(chains)
        percent = 0.0
        for chain in chains:
            p = job["progress"][chain]
            if p["state"] in ("done", "error"):
                percent += share
            elif p["total"]:
                percent += share * p["index"] / p["total"]
        job["percent"] = round(percent, 1)

    def _run(self, job_id: str, chains: list[str],
             categories: Optional[dict[str, list[str]]], use_cache: bool) -> None:
        job = self._jobs[job_id]

        def progress(chain: str, event: str, payload: dict) -> None:
            with self._lock:
                p = job["progress"][chain]
                if event == "start":
                    p["state"] = "running"
                elif event == "category":
                    p.update(index=payload["index"], total=payload["total"],
                             category=payload["category"], products=payload["products"])
                elif event == "done":
                    p.update(state="done", products=payload["products"])
                elif event == "error":
                    p.update(state="error", error=payload.get("message"))
                self._update_percent(job)

        try:
            result = run_scrape_job(chains, categories=categories, progress=progress,
                                    filename=f"productos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    use_cache=use_cache)
        except Exception as exc:
            log.exception("Job %s fallido", job_id)
            with self._lock:
                job.update(status="error", error=str(exc), finished_at=_now(), percent=100)
                self._save_history()
            return
        with self._lock:
            job.update(status="done", file=result["file"], products=result["products"],
                       percent=100, finished_at=_now())
            self._save_history()

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return json.loads(json.dumps(job)) if job else None

    def history(self) -> list[dict]:
        with self._lock:
            jobs = [j for j in self._jobs.values()]
        return sorted(jobs, key=lambda j: j["created_at"], reverse=True)


manager = JobManager()
