"""Tests de los parsers de cada cadena con productos crudos reales (fixtures)."""
import pytest

from scraper.models import Category, parse_es_price, normalize_unit
from scraper.scrapers.mercadona import MercadonaScraper
from scraper.scrapers.dia import DiaScraper
from scraper.scrapers.carrefour import CarrefourScraper
from scraper.scrapers.aldi import AldiScraper
from scraper.scrapers.lidl import LidlScraper


# ------------------------------------------------------------------ helpers
def make_scraper(cls):
    """Instancia un scraper sin tocar red ni disco."""
    scraper = cls.__new__(cls)  # evita __init__ (crearía sesiones/caché)
    return scraper


# ------------------------------------------------------------- parse helpers
@pytest.mark.parametrize("raw,expected", [
    ("1,49 €", 1.49),
    ("1.234,56 €", 1234.56),
    ("18.75", 18.75),
    (3.9, 3.9),
    ("", None),
    (None, None),
    ("precio no disponible", None),
])
def test_parse_es_price(raw, expected):
    assert parse_es_price(raw) == expected


def test_normalize_unit():
    assert normalize_unit("KILO") == "kg"
    assert normalize_unit("l") == "L"
    assert normalize_unit("unidad") == "ud"
    assert normalize_unit(None) is None


# --------------------------------------------------------------- Mercadona
MERCADONA_RAW = {
    "id": "4240",
    "display_name": "Aceite de oliva 0,4º Hacendado",
    "packaging": "Botella",
    "published": True,
    "share_url": "https://tienda.mercadona.es/product/4240/aceite-oliva",
    "unavailable_from": None,
    "_section": "Aceite de oliva",
    "price_instructions": {
        "unit_price": "3.90", "reference_price": "3.900", "reference_format": "L",
        "unit_size": 1.0, "size_format": "l", "price_decreased": True,
        "previous_unit_price": "4.15",
    },
}


def test_mercadona_parse():
    scraper = make_scraper(MercadonaScraper)
    cat = Category(id="112", name="Aceite, vinagre y sal", parent="Aceite, especias y salsas")
    p = scraper.parse_product(MERCADONA_RAW, cat)
    assert p.nombre == "Aceite de oliva 0,4º Hacendado (Botella)"
    assert p.marca == "Hacendado"
    assert p.precio == 3.90
    assert p.precio_unidad == 3.90
    assert p.unidad == "L"
    assert p.categoria == "Despensa"
    assert "4.15" in p.promocion
    assert p.disponible is True


def test_mercadona_unpublished_discarded():
    scraper = make_scraper(MercadonaScraper)
    cat = Category(id="112", name="x")
    assert scraper.parse_product({**MERCADONA_RAW, "published": False}, cat) is None


# --------------------------------------------------------------------- Dia
DIA_RAW = {
    "display_name": "Leche semidesnatada Dia Láctea pack 6 x 1 L",
    "brand": "Dia Láctea",
    "object_id": "504P6",
    "url": "/huevos-leche-y-mantequilla/leche/p/504P6",
    "units_in_stock": 673,
    "prices": {
        "price": 5.04, "price_per_unit": 0.84, "measure_unit": "LITRO",
        "strikethrough_price": 6.0, "is_promo_price": True,
        "is_club_price": False, "discount_percentage": 16,
    },
}


def test_dia_parse():
    scraper = make_scraper(DiaScraper)
    cat = Category(id="L2101", name="Leche", parent="Huevos leche y mantequilla")
    p = scraper.parse_product(DIA_RAW, cat)
    assert p.marca == "Dia Láctea"
    assert p.precio == 5.04
    assert p.precio_unidad == 0.84
    assert p.unidad == "L"
    assert p.categoria == "Lácteos y Huevos"
    assert p.url.startswith("https://www.dia.es/")
    assert "6.0" in p.promocion
    assert p.disponible is True


def test_dia_out_of_stock():
    scraper = make_scraper(DiaScraper)
    cat = Category(id="L1", name="Leche")
    p = scraper.parse_product({**DIA_RAW, "units_in_stock": 0}, cat)
    assert p.disponible is False


# --------------------------------------------------------------- Carrefour
CARREFOUR_RAW = {
    "name": "Banana a granel 1 Kg aprox",
    "brand": "MARCA NACIONAL SIN MARCA",
    "price": "1,49 €",
    "price_per_unit": "1,49 €",
    "measure_unit": "kg",
    "sku_id": "0358340000",
    "_ean": "2902266000009",
    "units_in_stock": 99,
    "url": "/supermercado/banana-a-granel-1-kg-aprox/R-529921745/p",
    "badge_map": {"promotions": [{"name": "-10% Acumulación"}]},
}


def test_carrefour_parse():
    scraper = make_scraper(CarrefourScraper)
    cat = Category(id="cat20002", name="Fruta", parent="Frescos")
    p = scraper.parse_product(CARREFOUR_RAW, cat)
    assert p.nombre == "Banana a granel 1 Kg aprox"
    assert p.marca is None  # "sin marca" se limpia
    assert p.precio == 1.49
    assert p.unidad == "kg"
    assert p.ean == "2902266000009"
    assert p.categoria == "Frutas y Verduras"
    assert p.promocion == "-10% Acumulación"
    assert p.url == "https://www.carrefour.es/supermercado/banana-a-granel-1-kg-aprox/R-529921745/p"


# -------------------------------------------------------------------- Aldi
ALDI_RAW = {
    "name": "Bastones de senderismo",
    "brand": "ADVENTURIDGE",
    "price_text": "14,99",
    "unit_text": "2 unidades par",
    "url": "https://www.aldi.es/producto/bastones-600334300.html",
    "_source": "ofertas",
}


def test_aldi_parse():
    scraper = make_scraper(AldiScraper)
    cat = Category(id="ofertas", name="Ofertas de la semana")
    p = scraper.parse_product(ALDI_RAW, cat)
    assert p.precio == 14.99
    assert p.marca == "ADVENTURIDGE"
    assert p.promocion == "Oferta semanal"
    assert p.unidad == "ud"


# -------------------------------------------------------------------- Lidl
LIDL_RAW = {
    "title": "Champiñones laminados",
    "fullTitle": "FRESHONA Champiñones laminados",
    "brand": {"name": "FRESHONA"},
    "erpNumber": "11008781",
    "canonicalPath": "/p/freshona-champinones-laminados/p11008781",
    "preventSelling": False,
    "price": {
        "price": 0.69, "oldPrice": 0.89,
        "packaging": {"text": "314 ml (170 g peso escurrido)"},
        "basePrice": {"text": "1 kg = 4,06 €"},
    },
}


def test_lidl_parse():
    scraper = make_scraper(LidlScraper)
    cat = Category(id="h10096095", name="Despensa", parent="Alimentación")
    p = scraper.parse_product(LIDL_RAW, cat)
    assert p.nombre == "FRESHONA Champiñones laminados (314 ml (170 g peso escurrido))"
    assert p.marca == "FRESHONA"
    assert p.precio == 0.69
    assert p.precio_unidad == 4.06
    assert p.unidad == "kg"
    assert p.categoria == "Despensa"
    assert "0.89" in p.promocion
    assert p.url == "https://www.lidl.es/p/freshona-champinones-laminados/p11008781"
