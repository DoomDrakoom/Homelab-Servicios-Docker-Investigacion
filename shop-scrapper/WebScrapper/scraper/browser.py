"""Soporte de navegador (Playwright) para cadenas cuyo contenido se renderiza con JS.

Se usa de forma perezosa: si Playwright no está instalado, los scrapers que lo
necesitan lanzan ScraperUnavailable con instrucciones, sin afectar al resto.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .base import ScraperUnavailable
from .http import DEFAULT_HEADERS

log = logging.getLogger("scraper.browser")

INSTALL_HINT = (
    "Este scraper necesita Playwright: pip install playwright && playwright install chromium"
)


class BrowserSession:
    """Página de Chromium headless reutilizable entre categorías."""

    def __init__(self, min_delay: float = 2.0) -> None:
        self.min_delay = min_delay
        self._pw = None
        self._browser = None
        self._page = None
        self._last_nav = 0.0
        self._consent_done = False

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScraperUnavailable(INSTALL_HINT) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        context = self._browser.new_context(
            user_agent=DEFAULT_HEADERS["User-Agent"],
            locale="es-ES",
            viewport={"width": 1366, "height": 900},
        )
        self._page = context.new_page()
        return self._page

    def _accept_consent(self, page) -> None:
        """Acepta el banner de cookies si existe (Usercentrics, OneTrust...).

        Muchas webs no cargan el contenido (o lo dejan tapado) hasta que hay
        consentimiento. Solo hace falta una vez por sesión de navegador.
        """
        if self._consent_done:
            return
        clicked = False
        try:
            clicked = page.evaluate("""
            () => {
              const uc = document.querySelector('#usercentrics-root');
              const ucBtn = uc && uc.shadowRoot &&
                uc.shadowRoot.querySelector('button[data-testid="uc-accept-all-button"]');
              if (ucBtn) { ucBtn.click(); return true; }
              const ot = document.querySelector('#onetrust-accept-btn-handler');
              if (ot) { ot.click(); return true; }
              const generic = [...document.querySelectorAll('button')]
                .find(b => /aceptar( todas| todo)?/i.test(b.innerText || ''));
              if (generic) { generic.click(); return true; }
              return false;
            }""")
        except Exception:
            pass
        if clicked:
            self._consent_done = True
            page.wait_for_timeout(1500)

    def extract(self, url: str, js: str, wait_selector: Optional[str] = None,
                scroll_steps: int = 6, timeout_ms: int = 45000,
                load_more_text: Optional[str] = None) -> Any:
        """Navega a la URL, hace scroll para forzar lazy-loading y evalúa `js`.

        load_more_text: si se indica, pulsa el botón "cargar más" que contenga
        ese texto tras cada tramo de scroll (grids paginados en cliente).
        """
        page = self._ensure_page()
        wait = self.min_delay - (time.time() - self._last_nav)
        if wait > 0:
            time.sleep(wait)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        self._last_nav = time.time()
        page.wait_for_timeout(1200)
        self._accept_consent(page)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=15000)
            except Exception:
                log.warning("[browser] no aparecio %r en %s", wait_selector, url)
        for _ in range(scroll_steps):
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(700)
            if load_more_text:
                button = page.query_selector(f'button:has-text("{load_more_text}")')
                if button:
                    try:
                        button.click()
                        page.wait_for_timeout(1500)
                    except Exception:
                        pass
        return page.evaluate(js)

    def get_content(self, url: str, timeout_ms: int = 45000) -> str:
        """Navega con el navegador real y devuelve el HTML crudo del servidor.

        Es la respuesta original (con los scripts de estado SSR intactos), no el
        DOM hidratado; ideal para leer window.__INITIAL_STATE__ y similares.
        """
        page = self._ensure_page()
        backoff = 5.0
        for attempt in range(4):
            wait = self.min_delay - (time.time() - self._last_nav)
            if wait > 0:
                time.sleep(wait)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            self._last_nav = time.time()
            if response is not None and response.status < 400:
                return response.text()
            status = response.status if response else "sin respuesta"
            log.warning("[browser] HTTP %s en %s (intento %d)", status, url, attempt + 1)
            # dejar respirar al WAF y que el challenge JS se asiente antes de reintentar
            page.wait_for_timeout(int(backoff * 1000))
            backoff = min(backoff * 2, 40)
        raise RuntimeError(f"HTTP {status} persistente en {url}")

    def fetch_text(self, url: str, timeout_ms: int = 45000) -> str:
        """GET con el stack de red de Chromium (evita bloqueos por huella TLS).

        No renderiza la página: útil para HTML SSR o APIs JSON tras un WAF.
        """
        page = self._ensure_page()
        wait = self.min_delay - (time.time() - self._last_nav)
        if wait > 0:
            time.sleep(wait)
        response = page.context.request.get(url, timeout=timeout_ms)
        self._last_nav = time.time()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status} en {url}")
        return response.text()

    def close(self) -> None:
        for closer in (self._browser, self._pw):
            try:
                if closer is not None:
                    closer.stop() if closer is self._pw else closer.close()
            except Exception:
                pass
        self._pw = self._browser = self._page = None


def tile_extraction_js(product_href_fragment: str) -> str:
    """JS genérico: recoge tarjetas de producto ancladas a enlaces de detalle."""
    return """
() => {
  const FRAG = %r;
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll(`a[href*="${FRAG}"]`)) {
    const href = a.href.split('#')[0];
    if (seen.has(href)) continue;
    const tile = a.closest('article') || a.closest('li') ||
      a.closest('div[class*="product"], div[class*="tile"], div[class*="card"], div[class*="item"]') || a;
    const text = (tile.innerText || '').trim();
    if (!text) continue;
    const img = tile.querySelector('img');
    let name = (a.getAttribute('title') || (img && img.alt) || '').trim();
    if (!name) {
      name = text.split('\\n').map(s => s.trim())
        .filter(s => s.length > 3 && !/\\d+[.,]\\d{2}\\s*€/.test(s))[0] || '';
    }
    const priceMatch = text.match(/(\\d+(?:[.,]\\d{1,2})?)\\s*€/);
    const ppuMatch = text.match(/(\\d+[.,]\\d{1,2})\\s*€?\\s*[\\/·]\\s*(kg|l|litro|ud|100\\s?g|100\\s?ml|m)\\b/i)
      || text.match(/\\((\\d+[.,]\\d{1,2})\\s*€\\s*(?:por|\\/)\\s*(kg|l|litro|ud)\\)/i);
    if (!name || !priceMatch) continue;
    seen.add(href);
    out.push({
      name, url: href,
      price_text: priceMatch[1],
      ppu_text: ppuMatch ? ppuMatch[1] : null,
      ppu_unit: ppuMatch ? ppuMatch[2] : null,
      text_sample: text.slice(0, 300),
    });
  }
  return out;
}
""" % (product_href_fragment,)
