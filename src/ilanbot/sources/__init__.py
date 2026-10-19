"""Kaynak kayıt defteri (registry)."""

from __future__ import annotations

from .base import ParseError, Source
from .ilan_gov import IlanGovSource
from .iskur import IskurSource
from .kamuilan_sbb import KamuIlanSbbSource
from .kariyer_kapisi import KariyerKapisiSource
from .yerel_yonetimler import YerelYonetimlerSource

# config.yaml'da tanınan tüm kaynak adları (uygulanmış olsun olmasın).
SOURCE_NAMES: tuple[str, ...] = (
    "kamuilan_sbb",
    "ilan_gov",
    "kariyer_kapisi",
    "iskur",
    "resmi_gazete",
    "yerel_yonetimler",
)

# Mesajlarda görünen kaynak adları.
DISPLAY_NAMES: dict[str, str] = {
    "kamuilan_sbb": "kamuilan.sbb.gov.tr",
    "ilan_gov": "ilan.gov.tr",
    "kariyer_kapisi": "kariyerkapisi.gov.tr",
    "iskur": "iskur.gov.tr",
    "resmi_gazete": "resmigazete.gov.tr",
    "yerel_yonetimler": "yerelyonetimler.csb.gov.tr",
}

# Uygulanmış kaynaklar. resmi_gazete kullanılamıyor (docs/kaynaklar.md), bilinçli olarak yok.
REGISTRY: dict[str, Source] = {
    s.name: s
    for s in (
        KamuIlanSbbSource(),
        IlanGovSource(),
        KariyerKapisiSource(),
        IskurSource(),
        YerelYonetimlerSource(),
    )
}

__all__ = ["DISPLAY_NAMES", "REGISTRY", "SOURCE_NAMES", "ParseError", "Source"]
