"""yerelyonetimler.csb.gov.tr — belediye personel alım duyuruları (HTML).

Ayrıntılar: docs/kaynaklar.md#yerel_yonetimler
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup, Tag

from ..dates import parse_tr_date
from ..http import get_with_retry
from ..models import Ilan, find_iller, normalize_education, normalize_il, normalize_kpss
from ..text import squash_spaces
from .base import BaseSource, ParseError, parse_rows

NAME = "yerel_yonetimler"
LIST_URL = "https://yerelyonetimler.csb.gov.tr/duyurular"

_ID_RE = re.compile(r"-(\d+)/?$")
# "İZMİR İLİ KARABAĞLAR BELEDİYE..." → "İZMİR"
_IL_PREFIX_RE = re.compile(r"^(\S+(?:\s\S+)?)\s+İLİ\b")


def parse(raw: str) -> list[Ilan]:
    soup = BeautifulSoup(raw, "lxml")
    rows = soup.select("a.duyurular-wrapper")
    if not rows and soup.select_one(".duyurular-slider, .photo-area") is None:
        raise ParseError("Duyuru listesi bulunamadı")
    return parse_rows(NAME, rows, _parse_row)


def _parse_row(a: Tag) -> Ilan:
    href = a["href"].strip()
    m = _ID_RE.search(href)
    if not m:
        raise ValueError(f"ID bulunamadı: {href!r}")
    title = squash_spaces(a.select_one(".info p").get_text(" "))
    title = title.removesuffix("...").rstrip(" .")
    if not title:
        raise ValueError("başlık boş")
    date_el = a.select_one(".date span")
    return Ilan(
        source=NAME,
        id=m.group(1),
        title=title,
        url=href,
        published_at=parse_tr_date(date_el.get_text(" ")) if date_el else None,
        education_levels=frozenset(normalize_education(title)),
        kpss_types=frozenset(normalize_kpss(title)),
        locations=frozenset(_locations(title)),
    )


def _locations(title: str) -> set[str]:
    if m := _IL_PREFIX_RE.match(title):
        il = normalize_il(m.group(1))
        if il:
            return {il}
    return find_iller(title)


class YerelYonetimlerSource(BaseSource):
    name = NAME
    display_name = "yerelyonetimler.csb.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        return parse(get_with_retry(client, LIST_URL).text)
