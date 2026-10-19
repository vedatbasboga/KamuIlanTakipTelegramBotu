"""kamuilan.sbb.gov.tr — Cumhurbaşkanlığı SBB kamu ilanları (HTML, ASP.NET WebForms).

Ayrıntılar: docs/kaynaklar.md#kamuilan_sbb
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag

from ..dates import month_number
from ..http import get_with_retry
from ..models import TZ, Ilan, find_iller, normalize_education, normalize_kpss
from ..models import now as _now
from ..text import squash_spaces, tr_upper
from .base import BaseSource, ParseError, parse_rows

NAME = "kamuilan_sbb"
BASE_URL = "https://kamuilan.sbb.gov.tr/"
# İlan linkleri (`ilanDetay.aspx?kod=...`) her istekte değişir ve Referer olmadan açılmaz;
# kullanıcıya ana sayfa linki verilir.
USER_URL = BASE_URL

# Logo src'sindeki "#19.10.2026 00:00:00" eki yayın tarihi DEĞİL, her satırda bugünün tarihi
# (önbellek kırıcı). ID'ye girerse ID her gün değişir; bu yüzden sadece dosya adı alınır.
_LOGO_RE = re.compile(r"logolar/([^/#?]+?)\.\w+(?:[#?].*)?$")
_RANGE_RE = re.compile(r"(\d{1,2})\s+([^\W\d_]+)\s*-\s*(\d{1,2})\s+([^\W\d_]+)")
_COUNT_RE = re.compile(r"(?<![\d.])(\d{1,4})\s+(?=[^\W\d_])")


def make_key(logo_id: str, published: datetime, institution: str, title: str) -> str:
    """Kararlı ID: site kalıcı ID vermediği için satırın değişmeyen alanlarından türetilir.

    CLAUDE.md kural 5'ten bilinçli sapma (kullanıcı kararı, docs/ILERLEME.md): başlık düzeltilirse
    ilan bir kez daha bildirilir.
    """
    norm = "|".join(
        [
            logo_id,
            f"{published:%Y-%m-%d}",
            tr_upper(squash_spaces(institution)),
            tr_upper(squash_spaces(title)),
        ]
    )
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def parse(raw: str, now: datetime | None = None) -> list[Ilan]:
    """Ana sayfa HTML'i → ilanlar.

    Liste, yayın gününe göre gruplanmış bir zaman çizelgesi: `li > time (h4 gün, h3 ay)` ve altında
    ilanlar (`a.xx`). Yıl yazmadığı için `now`'a göre çıkarılır (gelecekteki gün → geçen yıl).
    """
    now = now or _now()
    soup = BeautifulSoup(raw, "lxml")
    timeline = soup.find(id="nav2")
    if timeline is None:
        raise ParseError("İlan listesi (ul#nav2) bulunamadı")
    rows: list[tuple[datetime | None, Tag]] = []
    for group in timeline.find_all("li", recursive=False):
        published = _group_date(group, now)
        rows += [(published, a) for a in group.select("a.xx")]
    return parse_rows(NAME, rows, lambda row: _parse_row(*row))


def _group_date(group: Tag, now: datetime) -> datetime | None:
    time_el = group.find("time")
    if time_el is None or time_el.h4 is None or time_el.h3 is None:
        return None
    try:
        day = int(time_el.h4.get_text(strip=True))
    except ValueError:
        return None
    month = month_number(time_el.h3.get_text(strip=True))
    if month is None:
        return None
    year = now.year - 1 if (month, day) > (now.month, now.day) else now.year
    try:
        return datetime(year, month, day, tzinfo=TZ)
    except ValueError:
        return None


def _parse_row(published: datetime | None, a: Tag) -> Ilan:
    if published is None:
        raise ValueError("yayın günü (time) okunamadı")
    img = a.find("img")
    match = _LOGO_RE.search(img["src"]) if img else None
    if not match:
        raise ValueError("logo bulunamadı")
    logo_id = match.group(1)

    institution = squash_spaces(a.find("p", class_="alt_p1").get_text(" "))
    p2 = a.find("p", class_="alt_p2")
    em = p2.find("em")
    date_range = em.extract().get_text(" ") if em else ""
    title = squash_spaces(p2.get_text(" "))
    if not title:
        raise ValueError("başlık boş")

    return Ilan(
        source=NAME,
        id=make_key(logo_id, published, institution, title),
        title=title,
        url=USER_URL,
        institution=institution or None,
        published_at=published,
        deadline=_deadline(date_range, published),
        education_levels=frozenset(normalize_education(title)),
        kpss_types=frozenset(normalize_kpss(title)),
        locations=frozenset(find_iller(institution)),
        position_count=position_count(title),
    )


def _deadline(date_range: str, published: datetime | None) -> datetime | None:
    """ "( 19 Ekim - 2 Kasım)" → 2 Kasım 23:59. Yıl yayın tarihinden; ay geriye giderse +1."""
    m = _RANGE_RE.search(date_range)
    if not m or published is None:
        return None
    end_day, end_month = int(m.group(3)), month_number(m.group(4))
    if end_month is None:
        return None
    year = published.year
    if (end_month, end_day) < (published.month, published.day):
        year += 1
    try:
        return datetime(year, end_month, end_day, 23, 59, tzinfo=TZ)
    except ValueError:
        return None


def position_count(title: str) -> int | None:
    """ "6 UZMAN, 1 DESTEK PERSONELİ ALACAK" → 7. Yıl gibi sayılar (≥1900) sayılmaz."""
    if "ALACAK" not in tr_upper(title):
        return None
    counts = [int(n) for n in _COUNT_RE.findall(title) if int(n) < 1900]
    return sum(counts) or None


class KamuIlanSbbSource(BaseSource):
    name = NAME
    display_name = "kamuilan.sbb.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        return parse(get_with_retry(client, BASE_URL).text)
