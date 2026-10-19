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

# Uygulanmış kaynaklar. Parser'lar Aşama 4'te buraya eklenir.
REGISTRY: dict[str, Source] = {}

__all__ = ["REGISTRY", "SOURCE_NAMES", "ParseError", "Source"]
