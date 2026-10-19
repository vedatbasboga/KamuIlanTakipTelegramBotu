import json
from datetime import datetime

import httpx
import pytest
import respx
from conftest import fixture_json

from ilanbot.models import TZ, Ilan
from ilanbot.sources.base import ParseError
from ilanbot.sources.ilan_gov import (
    DETAIL_URL,
    LIST_URL,
    IlanGovSource,
    parse,
    parse_detail,
)

LIST = fixture_json("ilan_gov/list_personel_page1.json")


@pytest.fixture(scope="module")
def items():
    return parse(LIST)


def test_count_and_unique_ids(items):
    assert len(items) == 20
    assert len({i.id for i in items}) == 20


def test_first_item(items):
    first = items[0]
    assert first.source == "ilan_gov"
    assert first.id == "2261370"
    assert first.title == (
        "Türkiye İş Kurumu Genel Müdürlüğünden Sözleşmeli Bilişim Personeli Alım İlanı"
    )
    assert first.institution == "TÜRKİYE İŞ KURUMU GENEL MÜDÜRLÜĞÜ (İŞKUR)"
    assert first.url.startswith("https://www.ilan.gov.tr/ilan/2261370/")
    assert first.locations == {"ANKARA"}
    assert first.published_at == datetime(2026, 10, 19, 0, 0, 1, tzinfo=TZ)  # 21:00Z → TR 00:00
    assert first.summary == "Kategori: Sözleşmeli Bilişim Personeli İstihdamı"


def test_urls_have_no_spaces(items):
    kiyi = next(i for i in items if i.id == "2261344")
    assert " " not in kiyi.url and "%C2%A0" not in kiyi.url
    assert "kiyi-emniyeti-genel" in kiyi.url


def test_deadline_from_filters_when_present(items):
    with_deadline = [i for i in items if i.deadline]
    assert len(with_deadline) == 1
    assert with_deadline[0].deadline.tzinfo is not None


@pytest.mark.parametrize("raw", [{}, {"result": None}, {"result": {"ads": "x"}}, []])
def test_bad_structure_raises(raw):
    with pytest.raises(ParseError):
        parse(raw)


def test_parse_detail_extracts_kpss_and_education():
    base = Ilan(source="ilan_gov", id="2261370", title="t", url="https://x")
    enriched = parse_detail(fixture_json("ilan_gov/detail_2261370.json"), base)
    assert enriched.kpss_types == {"P3"}
    assert enriched.education_levels == {"lisans"}
    assert enriched.id == base.id


def test_parse_detail_empty_content_keeps_ilan():
    base = Ilan(source="ilan_gov", id="1", title="t", url="https://x")
    assert parse_detail({"result": {"content": ""}}, base) is base


@respx.mock
def test_list_items_request_shape():
    page1 = respx.post(LIST_URL).respond(200, json=LIST)
    with httpx.Client() as client:
        items = IlanGovSource().list_items(client)
    # 20 dolu sayfa → ikinci sayfa da istenir; mock ikisinde de aynı yanıtı verir (tekilleştirilir).
    assert page1.call_count == 2
    assert len(items) == 20
    req = page1.calls[0].request
    assert req.headers["X-Request-Origin"] == "IGT-UI"
    assert req.headers["X-Requested-With"] == "XMLHttpRequest"
    assert req.headers["Content-Type"] == "application/json-patch+json"
    assert json.loads(req.content) == {
        "keys": {"txv": ["8"]},
        "skipCount": 0,
        "maxResultCount": 20,
    }
    assert json.loads(page1.calls[1].request.content)["skipCount"] == 20


@respx.mock
def test_list_items_stops_on_short_page():
    short = {"result": {"ads": LIST["result"]["ads"][:5]}}
    route = respx.post(LIST_URL).respond(200, json=short)
    with httpx.Client() as client:
        assert len(IlanGovSource().list_items(client)) == 5
    assert route.call_count == 1


@respx.mock
def test_enrich_calls_detail_endpoint():
    route = respx.get(DETAIL_URL, params={"id": "2261370"}).respond(
        200, json=fixture_json("ilan_gov/detail_2261370.json")
    )
    base = Ilan(source="ilan_gov", id="2261370", title="t", url="https://x")
    with httpx.Client() as client:
        enriched = IlanGovSource().enrich(client, base)
    assert route.calls.last.request.headers["X-Request-Origin"] == "IGT-UI"
    assert enriched.kpss_types == {"P3"}
