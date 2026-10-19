"""Kaynak arayüzü, ortak taban sınıf ve hata tipleri."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Protocol, TypeVar

import httpx

from ..models import Ilan

log = logging.getLogger(__name__)

T = TypeVar("T")


class ParseError(Exception):
    """Yanıtta hiç ilan parse edilemedi; site yapısı değişmiş olabilir."""


class Source(Protocol):
    name: str  # registry anahtarı
    display_name: str  # mesajlarda görünen ad, ör. "kamuilan.sbb.gov.tr"
    # Bu kaynağın iki taraması arasındaki asgari süre (dakika). 0 = her çalışmada.
    min_interval_minutes: int

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        """Liste sayfası/API → ilanlar."""
        ...

    def enrich(self, client: httpx.Client, ilan: Ilan) -> Ilan:
        """Gerekiyorsa detay sayfasından eksik alanları doldurur; gerekmiyorsa aynen döndürür."""
        ...


class BaseSource:
    """Varsayılan davranışlar: her çalışmada taranır, detay zenginleştirmesi yok."""

    name: str
    display_name: str
    min_interval_minutes = 0

    def list_items(self, client: httpx.Client) -> list[Ilan]:  # pragma: no cover
        raise NotImplementedError

    def enrich(self, client: httpx.Client, ilan: Ilan) -> Ilan:
        return ilan


def parse_rows(source: str, rows: Iterable[T], parse_row: Callable[[T], Ilan | None]) -> list[Ilan]:
    """Satırları tek tek parse eder; bozuk satırı atlayıp uyarı loglar.

    `parse_row` bir satırı bilerek atlamak için (ör. süresi geçmiş ilan) None döndürebilir.
    Satır vardı ama hepsi hata verdiyse `ParseError` (site yapısı değişmiş demektir; sessizce
    "0 ilan" dönmek tehlikelidir). Aynı ID'li tekrarlar tekilleştirilir.
    """
    rows = list(rows)
    items: dict[str, Ilan] = {}
    failed = 0
    for i, row in enumerate(rows):
        try:
            ilan = parse_row(row)
        except Exception as e:  # tek satır tüm listeyi düşürmesin
            failed += 1
            log.warning(
                "[%s] %d. satır parse edilemedi: %s: %s", source, i + 1, type(e).__name__, e
            )
            continue
        if ilan is not None:
            items.setdefault(ilan.id, ilan)
    if rows and failed == len(rows):
        raise ParseError(f"{len(rows)} satırın hiçbiri parse edilemedi")
    return list(items.values())
