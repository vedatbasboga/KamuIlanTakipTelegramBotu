"""Kariyer Kapısı (kariyerkapisi.gov.tr) — herkese açık JSON API.

Ayrıntılar: docs/kaynaklar.md#kariyer_kapisi
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..dates import parse_iso
from ..http import request_with_retry
from ..models import Ilan, find_iller, normalize_education, normalize_kpss
from ..models import now as _now
from ..text import squash_spaces, tr_upper
from .base import BaseSource, ParseError, parse_rows

NAME = "kariyer_kapisi"
LIST_URL = "https://api.kariyerkapisi.gov.tr/api/ilan/SearchIlanPublic"
LIST_BODY = {"krM_ID": 0, "searchText": "", "il": "0", "ilanTuru": "0"}
DETAIL_URL = "https://kariyerkapisi.gov.tr/isealim/IlanDetay?i={guid}"
APPLY_ON_SITE = 1  # ilanTipi: 1 = Kariyer Kapısı üzerinden başvuru, 2 = dış link


def parse(raw: Any, now: datetime | None = None) -> list[Ilan]:
    """SearchIlanPublic yanıtı → ilanlar. Süresi geçmiş ilanlar atlanır (site de gizliyor)."""
    if not isinstance(raw, list):
        raise ParseError(f"Beklenen JSON dizisi, gelen: {type(raw).__name__}")
    now = now or _now()
    return parse_rows(NAME, raw, lambda row: _parse_row(row, now))


def _parse_row(row: dict[str, Any], now: datetime) -> Ilan | None:
    guid = row["guid"]
    deadline = parse_iso(row.get("bitTarih"))
    # Site, bitiş gününün sonuna kadar gösteriyor; biz de saat yerine güne bakıyoruz.
    if deadline and deadline.date() < now.date():
        return None

    institution = squash_spaces(row.get("kurumAdi") or "") or None
    title = squash_spaces(row["ilanBaslik"])
    # Başlıklar çoğunlukla "KURUM ADI - ASIL BAŞLIK" biçiminde; tekrarı at.
    if institution and tr_upper(title).startswith(tr_upper(institution) + " - "):
        title = title[len(institution) + 3 :].strip()

    if row.get("ilanTipi") == APPLY_ON_SITE or not row.get("basvuruLinki"):
        url = DETAIL_URL.format(guid=guid)
    else:
        url = row["basvuruLinki"].strip()

    category = squash_spaces((row.get("ilanTuru") or "").strip(" ,")) or None
    text = f"{title} {category or ''}"
    return Ilan(
        source=NAME,
        id=guid,
        title=title,
        url=url,
        institution=institution,
        published_at=parse_iso(row.get("basTarih")),
        deadline=deadline,
        education_levels=frozenset(normalize_education(text)),
        kpss_types=frozenset(normalize_kpss(title)),
        locations=frozenset(find_iller(institution)),
        summary=f"İlan türü: {category}" if category else None,
    )


class KariyerKapisiSource(BaseSource):
    name = NAME
    display_name = "kariyerkapisi.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        response = request_with_retry(
            client,
            "POST",
            LIST_URL,
            json=LIST_BODY,
            headers={"Origin": "https://kariyerkapisi.gov.tr"},
        )
        return parse(response.json())
