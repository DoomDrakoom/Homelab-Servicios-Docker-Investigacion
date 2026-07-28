"""Cliente HTTP con rate limiting por dominio, reintentos y backoff exponencial."""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests

log = logging.getLogger("scraper.http")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpError(Exception):
    """Fallo definitivo tras agotar los reintentos."""


class HttpClient:
    """Sesión requests con:

    - delay mínimo configurable entre peticiones al mismo dominio (+ jitter)
    - reintentos con backoff exponencial ante 429/5xx y errores de red
    - cabeceras realistas y cookies persistentes
    """

    def __init__(
        self,
        min_delay: float = 1.0,
        max_retries: int = 4,
        timeout: float = 30.0,
        headers: Optional[dict] = None,
        impersonate: Optional[str] = None,
    ) -> None:
        """impersonate: nombre de navegador para curl_cffi (p. ej. "chrome").

        Necesario en sitios cuyo WAF valida la huella TLS (p. ej. Akamai en
        Carrefour); requiere el paquete curl_cffi.
        """
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.timeout = timeout
        if impersonate:
            from curl_cffi import requests as cffi_requests
            self.session = cffi_requests.Session(impersonate=impersonate)
        else:
            self.session = requests.Session()
            self.session.headers.update(DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    def _throttle(self, url: str) -> None:
        domain = urlparse(url).netloc
        with self._lock:
            last = self._last_request.get(domain, 0.0)
            wait = self.min_delay + random.uniform(0, self.min_delay * 0.3) - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_request[domain] = time.time()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        backoff = 2.0
        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            self._throttle(url)
            try:
                resp = self.session.get(url, **kwargs)
            except Exception as exc:  # requests y curl_cffi usan jerarquías distintas
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("Error de red en %s (intento %d): %s", url, attempt + 1, exc)
            else:
                if resp.status_code < 400:
                    return resp
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code not in RETRYABLE_STATUS:
                    raise HttpError(f"{last_error} en {url}")
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 120))
                log.warning("HTTP %d en %s (intento %d)", resp.status_code, url, attempt + 1)
            if attempt < self.max_retries:
                time.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, 60)
        raise HttpError(f"Agotados los reintentos para {url} ({last_error})")

    def get_json(self, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("Accept", "application/json")
        return self.get(url, **kwargs).json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault(
            "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
        return self.get(url, **kwargs).text
