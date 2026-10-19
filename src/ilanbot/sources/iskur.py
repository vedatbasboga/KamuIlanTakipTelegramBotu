"""İŞKUR "Kamu Memur Alım İlanları" — il bazında HTML tablo.

Ayrıntılar: docs/kaynaklar.md#iskur. Tek istekte tüm iller alınamıyor: önce il listesinden
ilanı olan iller bulunur, sonra her biri ayrı çekilir (~18 istek, ~10 MB). Bu yüzden ve ilanların
çoğu kamuilan ile örtüştüğü için en fazla 3 saatte bir taranır (kullanıcı kararı).
"""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup, Tag

from ..dates import parse_tr_date
from ..http import get_with_retry
from ..models import Ilan, normalize_education, normalize_il, normalize_kpss
from ..text import squash_spaces
from .base import BaseSource, ParseError, parse_rows

NAME = "iskur"
SITE = "https://www.iskur.gov.tr"
LIST_URL = f"{SITE}/ilanlar/kamu-memur-alim-ilanlari/"

_COUNT_RE = re.compile(r"\((\d+)\)\s*$")
_MEDIA_ID_RE = re.compile(r"/medya/([^/]+)/")
_TRAILING_DATE_RE = re.compile(r"\s+\d{1,2}\.\d{1,2}\.\d{4}\s*$")


def parse_cities(raw: str) -> list[str]:
    """Parametresiz sayfadaki il seçiminden ilanı olan illerin adları ("Ankara (20)" → "Ankara")."""
    soup = BeautifulSoup(raw, "lxml")
    dropdown = soup.find(id="city-dropdown")
    if dropdown is None:
        raise ParseError("İl listesi (#city-dropdown) bulunamadı")
    cities = []
    for option in dropdown.find_all("option"):
        value = (option.get("value") or "").strip()
        m = _COUNT_RE.search(option.get_text(" ", strip=True))
        if value and m and int(m.group(1)) > 0:
            cities.append(value)
    return cities


def parse(raw: str, city: str) -> list[Ilan]:
    """Bir ilin ilan tablosu → ilanlar."""
    soup = BeautifulSoup(raw, "lxml")
    il = normalize_il(city)
    return parse_rows(NAME, soup.select("tr.clickable-row"), lambda row: _parse_row(row, il))


def _parse_row(row: Tag, il: str | None) -> Ilan:
    file_url = (row.get("data-file-url") or "").strip()
    m = _MEDIA_ID_RE.search(file_url)
    if not m:
        raise ValueError(f"medya ID'si yok: {file_url!r}")
    cells = row.find_all("td")
    deadline = parse_tr_date(cells[0].get_text(" ", strip=True))
    title = _TRAILING_DATE_RE.sub("", squash_spaces(cells[1].get_text(" ")))
    if not title:
        raise ValueError("başlık boş")
    return Ilan(
        source=NAME,
        id=m.group(1),
        title=title,
        url=SITE + quote(file_url, safe="/-_.~"),
        deadline=deadline,
        education_levels=frozenset(normalize_education(title)),
        kpss_types=frozenset(normalize_kpss(title)),
        locations=frozenset({il}) if il else frozenset(),
    )


class IskurSource(BaseSource):
    name = NAME
    display_name = "iskur.gov.tr"
    min_interval_minutes = 180

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        cities = parse_cities(get_with_retry(client, LIST_URL).text)
        items: dict[str, Ilan] = {}
        for city in cities:
            page = get_with_retry(client, LIST_URL, params={"il": city}).text
            for ilan in parse(page, city):
                items.setdefault(ilan.id, ilan)
        return list(items.values())
