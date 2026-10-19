from datetime import datetime

import httpx
import pytest
import respx
from conftest import fixture_text

from ilanbot.models import TZ
from ilanbot.sources.base import ParseError
from ilanbot.sources.iskur import LIST_URL, IskurSource, parse, parse_cities

INDEX = fixture_text("iskur/memur_index.html")
ANKARA = fixture_text("iskur/memur_ankara.html")


@pytest.fixture(scope="module")
def items():
    return parse(ANKARA, "Ankara")


def test_cities_with_ilan():
    cities = parse_cities(INDEX)
    assert len(cities) == 17
    assert "Ankara" in cities and "İstanbul" in cities and "Iğdır" in cities
    assert "Adana" not in cities  # ilanı yok


def test_cities_missing_dropdown_raises():
    with pytest.raises(ParseError):
        parse_cities("<html></html>")


def test_count_and_unique_ids(items):
    assert len(items) == 20
    assert len({i.id for i in items}) == 20


def test_first_item(items):
    first = items[0]
    assert first.source == "iskur"
    assert first.id == "lk5crcmz"
    assert first.title == "Tapu ve Kadastro Genel Müdürlüğü Sözleşmeli Bilişim Personeli Alım İlanı"
    assert first.url.startswith("https://www.iskur.gov.tr/medya/lk5crcmz/")
    assert first.deadline == datetime(2026, 10, 19, 17, 0, tzinfo=TZ)
    assert first.locations == {"ANKARA"}


def test_empty_city_page_is_empty():
    assert parse(INDEX, "Adana") == []


@respx.mock
def test_list_items_fetches_each_city():
    def respond(request):
        city = request.url.params.get("il")
        return httpx.Response(200, text=ANKARA if city == "Ankara" else INDEX)

    route = respx.get(url__startswith=LIST_URL).mock(side_effect=respond)
    with httpx.Client() as client:
        items = IskurSource().list_items(client)
    assert route.call_count == 1 + 17
    assert route.calls[1].request.url.params["il"] == "Ağrı"
    assert len(items) == 20
