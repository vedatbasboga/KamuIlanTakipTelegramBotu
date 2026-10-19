import re
from datetime import datetime

import httpx
import pytest
import respx
from conftest import FIXTURE_NOW, fixture_text

from ilanbot.models import TZ
from ilanbot.sources.base import ParseError
from ilanbot.sources.kamuilan_sbb import BASE_URL, KamuIlanSbbSource, parse, position_count

HTML = fixture_text("kamuilan_sbb/list.html")


@pytest.fixture(scope="module")
def items():
    return parse(HTML, FIXTURE_NOW)


def test_count_and_unique_ids(items):
    assert len(items) == 98
    assert len({i.id for i in items}) == 98


def test_first_item(items):
    first = items[0]
    assert first.source == "kamuilan_sbb"
    assert re.fullmatch(r"[0-9a-f]{16}", first.id)
    assert first.institution == "DİCLE ÜNİVERSİTESİ"
    assert first.title == "9 ÖĞRETİM ELEMANI ALACAK"
    assert first.url == "https://kamuilan.sbb.gov.tr/"
    assert first.published_at == datetime(2026, 10, 19, tzinfo=TZ)
    assert first.deadline == datetime(2026, 11, 2, 23, 59, tzinfo=TZ)
    assert first.position_count == 9
    assert all(i.published_at.tzinfo and i.deadline.tzinfo for i in items)


def test_belediye_rows_without_logo_date(items):
    # Belediye satırlarında logo BEL2.png ve tarih eki yok; yayın günü zaman çizelgesinden gelir.
    kesan = next(i for i in items if i.institution == "KEŞAN BELEDİYE BAŞKANLIĞI")
    assert kesan.published_at == datetime(2026, 10, 16, tzinfo=TZ)
    assert kesan.deadline == datetime(2026, 11, 19, 23, 59, tzinfo=TZ)


def test_year_is_inferred_from_now(items):
    gib = next(i for i in items if i.institution == "GELİR İDARESİ BAŞKANLIĞI")
    assert gib.published_at == datetime(2026, 8, 3, tzinfo=TZ)
    # Ocak'ta bakılınca "3 Ağustos" geçen yıla aittir.
    later = parse(HTML, datetime(2027, 1, 5, tzinfo=TZ))
    assert next(i for i in later if i.title == gib.title).published_at.year == 2026


def test_ids_stable_when_cache_buster_changes(items):
    # Logo src'sindeki "#19.10.2026" eki her gün değişir; ID'ler değişmemeli.
    tomorrow = parse(HTML.replace("#19.10.2026", "#20.10.2026"), FIXTURE_NOW)
    assert {i.id for i in tomorrow} == {i.id for i in items}


def test_locations_from_institution(items):
    kku = next(i for i in items if i.institution == "KIRIKKALE ÜNİVERSİTESİ")
    assert kku.locations == {"KIRIKKALE"}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("153 SÖZLEŞMELİ PERSONEL ALACAK", 153),
        ("6 UZMAN, 1 DESTEK PERSONELİ ALACAK", 7),
        ("10 FON DENETÇİ YARDIMCISI, 45 FON UZMAN YARDIMCISI VE 20 FON AVUKATI ALACAK", 75),
        ("2026 YILI MUVAZZAF SUBAY ADAYI TEMİNİ", None),
        ("DÜZELTME İLANI", None),
        ("11  ALACAK", 11),  # unvan boş ama sayı doğru
    ],
)
def test_position_count(title, expected):
    assert position_count(title) == expected


def test_missing_list_raises():
    with pytest.raises(ParseError):
        parse("<html><body>bakım çalışması</body></html>", FIXTURE_NOW)


def test_broken_rows_raise():
    broken = re.sub(r"<img[^>]*>", "", HTML)  # logo yok → hiçbir satır parse edilemez
    with pytest.raises(ParseError):
        parse(broken, FIXTURE_NOW)


@respx.mock
def test_list_items_fetches_home_page():
    route = respx.get(BASE_URL).respond(200, text=HTML)
    with httpx.Client() as client:
        items = KamuIlanSbbSource().list_items(client)
    assert route.called
    assert len(items) == 98
