"""Kaynak kayıt defteri (registry)."""

from __future__ import annotations

from .base import ParseError, Source

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
    "kariyer_kapisi": "kariyerkapisi.cbiko.gov.tr",
    "iskur": "iskur.gov.tr",
    "resmi_gazete": "resmigazete.gov.tr",
    "yerel_yonetimler": "yerelyonetimler.csb.gov.tr",
}

# Uygulanmış kaynaklar. Parser'lar Aşama 4'te buraya eklenir.
REGISTRY: dict[str, Source] = {}

__all__ = ["DISPLAY_NAMES", "REGISTRY", "SOURCE_NAMES", "ParseError", "Source"]
