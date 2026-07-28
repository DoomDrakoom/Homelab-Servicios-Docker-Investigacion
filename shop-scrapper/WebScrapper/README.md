# Supermercados Scraper

Scraper modular de supermercados españoles que exporta el catálogo a un Excel
clasificado por categoría, lanzable desde una interfaz web con progreso en vivo.

## Cadenas soportadas y estrategia técnica

| Cadena | Estrategia | Cobertura | EAN |
|---|---|---|---|
| **Mercadona** | API JSON (`tienda.mercadona.es/api/`) | Catálogo completo (~160 subcategorías) | — |
| **Dia** | JSON embebido (`vike_pageContext`) en páginas de categoría SSR | Catálogo casi completo (272 subcategorías, máx. 5 páginas/subcategoría por robots.txt) | — |
| **Carrefour** | `window.__INITIAL_STATE__` en páginas SSR, vía `curl_cffi` imitando el TLS de Chrome (su WAF Akamai bloquea clientes normales) | Catálogo completo del supermercado (~99 categorías) | ✔ (del array de analítica) |
| **Lidl** | Payload `__NUXT_DATA__` (formato devalue) de las páginas de Alimentación | Solo productos destacados online (~200); los precios de tienda física viven en la app Lidl Plus | — |
| **Aldi** | Playwright (Chromium headless): la web es 100 % JS | Ofertas semanales (~220) + surtido publicado (~360 fichas, lento) | — |

> **Nota sobre "abasthosour"**: cadena pendiente de identificar. Cuando se aclare
> cuál es, añadirla cuesta un fichero (ver [Añadir una cadena nueva](#añadir-una-cadena-nueva)).

## Requisitos

- Python 3.11+ (probado con 3.13)
- Para Aldi: Chromium de Playwright (`playwright install chromium`)

## Instalación

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows  |  source .venv/bin/activate en Linux
pip install -r requirements.txt
playwright install chromium   # solo necesario para Aldi
```

## Uso

### Interfaz web

```bash
uvicorn app.main:app --port 8000
```

Abre `http://localhost:8000`: selecciona cadenas (y opcionalmente categorías),
pulsa **Lanzar scraping** y sigue el progreso por cadena en vivo (SSE). Al
terminar aparece el enlace de descarga del `.xlsx` y la ejecución queda en el
historial.

### CLI

```bash
python -m scraper --chains mercadona,dia            # cadenas completas
python -m scraper --chains mercadona --categories 112,156
python -m scraper --chains carrefour --no-cache     # ignora la caché
```

### API REST

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/chains` | Cadenas disponibles |
| GET | `/api/chains/{id}/categories` | Categorías nativas de una cadena (en vivo, cacheado 1 h) |
| POST | `/api/scrape` | `{"chains": ["mercadona"], "categories": {"mercadona": ["112"]}, "use_cache": true}` → `{"job_id"}` |
| GET | `/api/status/{job_id}` | Estado del job |
| GET | `/api/events/{job_id}` | Progreso en vivo (Server-Sent Events) |
| GET | `/api/download/{job_id}` | Descarga del Excel |
| GET | `/api/jobs` | Historial de ejecuciones |

## Salida Excel

`data/exports/productos_YYYYMMDD.xlsx` (con hora si se lanza desde la web):

- Hoja **"Todos"** con todos los productos; tabla con autofiltro y cabecera congelada.
- Una hoja por **categoría unificada** (Frutas y Verduras, Carne, Despensa...).
- Columnas: cadena, nombre, marca, categoría unificada, categoría nativa,
  precio, precio/unidad, unidad (kg/L/ud), EAN, disponible, promoción, URL,
  fecha de extracción.
- Los precios son celdas numéricas con formato de moneda (no texto); los
  decimales con coma y el símbolo € de las webs se normalizan al parsear.

## Resiliencia

- **Rate limiting por dominio** (1–2 s + jitter, configurable por scraper vía
  `min_delay`) y **backoff exponencial** ante 429/5xx o errores de red, con
  respeto de `Retry-After`.
- **Caché en disco** (`data/raw/{cadena}.json`), escrita categoría a categoría
  de forma atómica: si un scrape muere a mitad, relanzar reutiliza lo ya
  descargado (validez por defecto: 12 h). `use_cache=false` fuerza descarga.
- Sesiones con cookies y User-Agent realista; deduplicación por URL.
- Un fallo en una categoría o cadena no aborta el job: se registra y se continúa.

## Docker (homelab / Nginx Proxy Manager)

```bash
docker compose up -d --build
```

- Puerto interno **8000**; publicado en el host como **8410** (edítalo en
  `docker-compose.yml`).
- Variables de entorno: `LOG_LEVEL` (`INFO` por defecto).
- Volumen `./data:/app/data`: caché, Excel generados e historial persisten.
- En NPM crea un proxy host hacia `super-scraper:8000` (misma red Docker) o
  `IP_DEL_HOST:8410`, y **activa el soporte de streaming/WebSockets** para que
  los eventos SSE de progreso no se corten.

## Añadir una cadena nueva

1. Crea `scraper/scrapers/micadena.py`:

```python
from ..base import BaseScraper
from ..category_map import unify_category
from ..models import Category, Product, parse_es_price

class MiCadenaScraper(BaseScraper):
    chain_id = "micadena"
    chain_name = "Mi Cadena"
    min_delay = 1.5          # segundos entre peticiones al dominio

    def list_categories(self) -> list[Category]: ...
    def list_products(self, category) -> list[dict]: ...   # dicts crudos
    def parse_product(self, raw, category) -> Product | None: ...
```

2. Regístrala en `scraper/registry.py` (una línea en `SCRAPERS`).
3. Añade un test de parser en `tests/test_parsers.py` con un producto crudo real.

Con eso hereda gratis: caché reanudable, rate limiting, reintentos, progreso,
UI web, Excel y CLI. Consejos:

- **Busca primero una API JSON** (pestaña Red del navegador, backend de su app
  móvil). Si no hay, mira si el HTML servido lleva el estado embebido
  (`__INITIAL_STATE__`, `__NEXT_DATA__`, `__NUXT_DATA__` — hay decodificador en
  `scraper/nuxt.py`). Solo como último recurso usa Playwright
  (`scraper/browser.py`, ver el adapter de Aldi).
- Si el sitio bloquea con 403 pese a cabeceras correctas, suele ser huella TLS:
  usa `HttpClient(impersonate="chrome")` como Carrefour.

## Tests

```bash
pytest            # parsers de las 5 cadenas + exportador Excel (sin red)
```

## Límites y consideraciones legales

- Solo se extraen **datos públicos de producto y precio**, con delays
  conservadores para no molestar a los servidores.
- robots.txt: se respetan las rutas excluidas relevantes (p. ej. Dia limita la
  paginación a `pag-5`, y así se hace). Excepción documentada: el robots.txt de
  Mercadona excluye `/api` para crawlers; este proyecto hace un volumen bajo
  (~160 peticiones por scrape completo) contra la API pública de su tienda.
  Revisa los ToS de cada sitio antes de un uso intensivo o comercial.
- Los precios de Carrefour/Dia/Mercadona pueden variar por código postal o
  almacén; se raspan los de la tienda por defecto (Mercadona admite
  `MercadonaScraper(warehouse="...")`).
- Lidl y Aldi no publican su surtido completo de tienda física en la web: la
  cobertura es parcial por diseño de sus webs, no por limitación del scraper.
