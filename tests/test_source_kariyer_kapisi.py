import json
from datetime import datetime

import httpx
import pytest
import respx
from conftest import FIXTURE_NOW, fixture_json

from ilanbot.models import TZ
from ilanbot.sources.base import ParseError
from ilanbot.sources.kariyer_kapisi import LIST_URL, KariyerKapisiSource, parse

DATA = fixture_json("kariyer_kapisi/search_ilan_public.json")


@pytest.fixture(scope="module")
def items():
    return parse(DATA, FIXTURE_NOW)


def test_count_and_unique_ids(items):
    assert len(items) == 20
    assert len({i.id for i in items}) == 20


def test_first_item(items):
    first = items[0]
    assert first.source == "kariyer_kapisi"
    assert first.id == "12c5b0ac-cd05-4316-9d7c-39ed4d06a358"
    assert first.institution == "TAPU VE KADASTRO GENEL MÜDÜRLÜĞÜ"
    # "KURUM - BAŞLIK" önekindeki tekrar atılır.
    assert first.title == "SÖZLEŞMELİ BİLİŞİM PERSONELİ ALIM İLANI (2026)"
    assert first.url == (
        "https://kariyerkapisi.gov.tr/isealim/IlanDetay?i=12c5b0ac-cd05-4316-9d7c-39ed4d06a358"
    )
    assert first.published_at == datetime(2026, 10, 12, 9, 0, tzinfo=TZ)
    assert first.deadline == datetime(2026, 10, 19, 17, 0, tzinfo=TZ)
    assert first.summary == "İlan türü: Sözleşmeli Personel İlanları"


def test_external_link_and_trailing_comma(items):
    msb = next(i for i in items if i.id == "39d5a688-3b17-48de-a123-9140f55af29e")
    assert msb.url.startswith("https://personeltemin.msb.gov.tr/")
    assert msb.summary == "İlan türü: Askeri Personel İlanları"


def test_expired_items_are_skipped():
    later = parse(DATA, datetime(2026, 10, 25, tzinfo=TZ))
    assert len(later) < 20
    assert all(i.deadline is None or i.deadline.date() >= later_date() for i in later)


def later_date():
    return datetime(2026, 10, 25, tzinfo=TZ).date()


def test_all_expired_is_empty_not_error():
    assert parse(DATA, datetime(2030, 1, 1, tzinfo=TZ)) == []


@pytest.mark.parametrize("raw", [{}, None, "x"])
def test_bad_structure_raises(raw):
    with pytest.raises(ParseError):
        parse(raw, FIXTURE_NOW)


def test_rows_missing_fields_raise():
    with pytest.raises(ParseError):
        parse([{"foo": 1}, {"bar": 2}], FIXTURE_NOW)


@respx.mock
def test_list_items_request_shape():
    route = respx.post(LIST_URL).respond(200, json=DATA)
    with httpx.Client() as client:
        KariyerKapisiSource().list_items(client)
    assert json.loads(route.calls.last.request.content) == {
        "krM_ID": 0,
        "searchText": "",
        "il": "0",
        "ilanTuru": "0",
    }
