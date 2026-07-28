"""Caché en disco por cadena para poder reanudar scrapes interrumpidos.

Estructura del fichero data/raw/{cadena}.json:
{
  "categories": {
    "<cat_id>": {"fetched_at": "...", "items": [ ...productos crudos... ]}
  }
}
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class RawCache:
    def __init__(self, chain_id: str, base_dir: str | Path = "data/raw", max_age_hours: float = 12.0) -> None:
        self.path = Path(base_dir) / f"{chain_id}.json"
        self.max_age_hours = max_age_hours
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass
        return {"categories": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Escritura atómica: tmp + replace, para no corromper la caché si se interrumpe
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def get(self, category_id: str) -> Optional[list]:
        """Devuelve los items cacheados de la categoría si aún son válidos."""
        entry = self._data["categories"].get(str(category_id))
        if not entry:
            return None
        try:
            fetched = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, ValueError):
            return None
        age = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        if age > self.max_age_hours:
            return None
        return entry["items"]

    def set(self, category_id: str, items: list) -> None:
        with self._lock:
            self._data["categories"][str(category_id)] = {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "items": items,
            }
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._data = {"categories": {}}
            if self.path.exists():
                self.path.unlink()
