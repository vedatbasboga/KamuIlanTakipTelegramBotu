"""Kaynak arayüzü ve ortak hata tipleri."""

from __future__ import annotations

from typing import Protocol

import httpx

from ..models import Ilan


class ParseError(Exception):
    """Yanıtta hiç ilan parse edilemedi; site yapısı değişmiş olabilir."""


class Source(Protocol):
    name: str  # registry anahtarı
    display_name: str  # mesajlarda görünen ad, ör. "kamuilan.sbb.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]:
        """Liste sayfası/API → ilanlar."""
        ...

    def enrich(self, client: httpx.Client, ilan: Ilan) -> Ilan:
        """Gerekiyorsa detay sayfasından eksik alanları doldurur; gerekmiyorsa aynen döndürür."""
        ...
