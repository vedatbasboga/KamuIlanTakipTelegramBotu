from datetime import datetime

import httpx
import pytest
import respx
from conftest import fixture_text

from ilanbot.models import TZ
from ilanbot.sources.base import ParseError
from ilanbot.sources.yerel_yonetimler import LIST_URL, YerelYonetimlerSource, parse

HTML = fixture_text("yerel_yonetimler/duyurular_page1.html")


@pytest.fixture(scope="module")
def items():
    return parse(HTML)


def test_count_and_unique_ids(items):
    assert len(items) == 12
    assert len({i.id for i in items}) == 12


def test_first_item(items):
    first = items[0]
    assert first.source == "yerel_yonetimler"
    assert first.id == "478289"
    assert first.title == (
        "İZMİR İLİ KARABAĞLAR BELEDİYE BAŞKANLIĞINA İLK DEFA ATANMAK ÜZERE SÖZLEŞMELİ "
        "PERSONEL ALIM İLANI"
    )
    assert not first.title.endswith(".")
    assert first.url.startswith("https://yerelyonetimler.csb.gov.tr/")
    assert first.published_at == datetime(2026, 10, 16, tzinfo=TZ)
    assert first.locations == {"İZMİR"}


def test_locations_without_ili_prefix(items):
    rize = next(i for i in items if i.id == "478083")
    assert rize.locations == {"RİZE"}


def test_missing_list_raises():
    with pytest.raises(ParseError):
        parse("<html><body>hata</body></html>")


@respx.mock
def test_list_items():
    route = respx.get(LIST_URL).respond(200, text=HTML)
    with httpx.Client() as client:
        assert len(YerelYonetimlerSource().list_items(client)) == 12
    assert route.called
