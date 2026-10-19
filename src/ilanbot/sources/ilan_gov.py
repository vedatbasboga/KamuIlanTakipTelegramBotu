"""ilan.gov.tr — Basın İlan Kurumu, "Kamu-Akademik Personel" kategorisi (JSON API).

Ayrıntılar: docs/kaynaklar.md#ilan_gov. Sunucu ara sertifikayı göndermiyor; zincir
`ilanbot/certs/` ile tamamlanır (bkz. `http.ssl_context`).
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from ..dates import parse_iso, parse_tr_date
from ..http import get_with_retry, request_with_retry
from ..models import Ilan, normalize_education, normalize_il, normalize_kpss
from ..text import squash_spaces
from .base import BaseSource, ParseError, parse_rows

NAME = "ilan_gov"
SITE = "https://www.ilan.gov.tr"
LIST_URL = f"{SITE}/api/api/services/app/Ad/AdsByFilter"
DETAIL_URL = f"{SITE}/api/api/services/app/AdDetail/GetAdDetail"
PERSONNEL_CATEGORY = "8"  # "Kamu-Akademik Personel" (taxId)
PAGE_SIZE = 20  # sunucu daha fazlasını döndürmüyor
PAGES = 2
# İkisi birlikte yoksa API boş gövdeli 403 döner (docs/kaynaklar.md).
API_HEADERS = {
    "Accept": "text/plain",
    "X-Request-Origin": "IGT-UI",
    "X-Requested-With": "XMLHttpRequest",
}

_DEADLINE_RE = re.compile(r"(?i)son\s+başvuru(?:\s+tarihi)?\s*[:\-]?\s*(.{0,40})")


def _filter_value(ad: dict[str, Any], field: str, key: str) -> str | None:
    for item in ad.get(field) or []:
        if item.get("key") == key and item.get("value"):
            return str(item["value"]).strip()
    return None


def parse(raw: Any) -> list[Ilan]:
    """AdsByFilter yanıtı → ilanlar."""
    try:
        ads = raw["result"]["ads"]
    except (TypeError, KeyError) as e:
        raise ParseError(f"Beklenmeyen yanıt yapısı: {e!r}") from None
    if not isinstance(ads, list):
        raise ParseError("result.ads bir liste değil")
    return parse_rows(NAME, ads, _parse_row)


def _parse_row(ad: dict[str, Any]) -> Ilan:
    ad_id = str(ad["id"]).strip()
    if not ad_id or ad_id == "0":
        raise ValueError("id yok")
    title = squash_spaces(ad["title"])
    il = normalize_il(ad.get("addressCityName"))
    category = _filter_value(ad, "values", "Kategori")
    deadline_raw = _filter_value(ad, "adTypeFilters", "Son başvuru Tarihi")
    return Ilan(
        source=NAME,
        id=ad_id,
        title=title,
        # urlStr'de bazen boşluk/bölünmez boşluk var ("kiyi\xa0emniyeti"); site ID ile açıyor.
        url=SITE + quote(re.sub(r"\s+", "-", ad["urlStr"].strip()), safe="/-_.~"),
        institution=squash_spaces(ad.get("advertiserName") or "") or None,
        published_at=parse_iso(ad.get("publishStartDate")),
        deadline=parse_tr_date(deadline_raw),
        education_levels=frozenset(normalize_education(title)),
        kpss_types=frozenset(normalize_kpss(title)),
        locations=frozenset({il}) if il else frozenset(),
        summary=f"Kategori: {category}" if category else None,
    )


def parse_detail(raw: Any, ilan: Ilan) -> Ilan:
    """GetAdDetail yanıtındaki tam metinden öğrenim, KPSS ve (bulunursa) son başvuruyu ekler."""
    content = (raw.get("result") or {}).get("content") or ""
    text = squash_spaces(BeautifulSoup(content, "lxml").get_text(" "))
    if not text:
        return ilan
    deadline = ilan.deadline
    if deadline is None and (m := _DEADLINE_RE.search(text)):
        deadline = parse_tr_date(m.group(1))
    return dataclasses.replace(
        ilan,
        education_levels=ilan.education_levels | normalize_education(text),
        kpss_types=ilan.kpss_types | normalize_kpss(text),
        deadline=deadline,
    )


class IlanGovSource(BaseSource):
    name = NAME
    display_name = "ilan.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        items: dict[str, Ilan] = {}
        for page in range(PAGES):
            body = {
                "keys": {"txv": [PERSONNEL_CATEGORY]},
                "skipCount": page * PAGE_SIZE,
                "maxResultCount": PAGE_SIZE,
            }
            response = request_with_retry(
                client,
                "POST",
                LIST_URL,
                json=body,
                headers={**API_HEADERS, "Content-Type": "application/json-patch+json"},
            )
            page_items = parse(response.json())
            for ilan in page_items:
                items.setdefault(ilan.id, ilan)
            if len(page_items) < PAGE_SIZE:
                break
        return list(items.values())

    def enrich(self, client: httpx.Client, ilan: Ilan) -> Ilan:
        response = get_with_retry(client, DETAIL_URL, params={"id": ilan.id}, headers=API_HEADERS)
        return parse_detail(response.json(), ilan)
