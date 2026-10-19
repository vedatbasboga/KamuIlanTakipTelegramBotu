"""Türkçe-duyarlı metin yardımcıları.

`str.lower()` / `str.casefold()` Türkçe `İ/ı` harflerini doğru işlemez
("İ".lower() == "i̇", "I".lower() == "i"). Bu modül tüm modüllerde ortak kullanılır.
"""

from __future__ import annotations

import re

_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})
_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})
_ASCII_MAP = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "â": "a",
        "î": "i",
        "û": "u",
        "Ç": "C",
        "Ğ": "G",
        "İ": "I",
        "Ö": "O",
        "Ş": "S",
        "Ü": "U",
        "Â": "A",
        "Î": "I",
        "Û": "U",
    }
)
_SPACE_RE = re.compile(r"\s+")


def tr_lower(text: str) -> str:
    """Türkçe kurallarıyla küçük harfe çevirir: I→ı, İ→i."""
    return text.translate(_LOWER_MAP).lower()


def tr_upper(text: str) -> str:
    """Türkçe kurallarıyla büyük harfe çevirir: i→İ, ı→I."""
    return text.translate(_UPPER_MAP).upper()


def ascii_fold(text: str) -> str:
    """Türkçe karakterleri ASCII karşılıklarına indirger (ç→c, ğ→g, ı→i, ...)."""
    return text.translate(_ASCII_MAP)


def squash_spaces(text: str) -> str:
    """Ardışık boşlukları teke indirir, baştaki/sondaki boşlukları atar."""
    return _SPACE_RE.sub(" ", text).strip()


def fold_for_match(text: str) -> str:
    """Karşılaştırma anahtarı: Türkçe küçük harf + boşluk sadeleştirme."""
    return squash_spaces(tr_lower(text))


def contains_keyword(text: str, keyword: str) -> bool:
    """`keyword` metinde geçiyor mu? Türkçe-duyarlı, büyük/küçük harf duyarsız."""
    needle = fold_for_match(keyword)
    if not needle:
        return False
    return needle in fold_for_match(text)
