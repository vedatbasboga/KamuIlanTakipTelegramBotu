"""İlan filtreleri.

Kurallar VE ile bağlanır; listesi boş kural atlanır. Öğrenim/KPSS/il alanı ilanda yoksa karar
`filtre_belirsizse_gonder`'e kalır (CLAUDE.md kural 6). `exclude_keywords` her zaman önceliklidir.
"""

from __future__ import annotations

from collections.abc import Iterable

from .config import FiltersConfig
from .models import Ilan
from .text import contains_keyword

# Bu ifadeler geçen ilanlar her il filtresiyle eşleşir.
NATIONWIDE_PHRASES = ("türkiye geneli", "tüm iller", "tüm türkiye", "81 il")


def ilan_text(ilan: Ilan) -> str:
    return " ".join(p for p in (ilan.title, ilan.institution, ilan.summary) if p)


def matches(ilan: Ilan, f: FiltersConfig) -> tuple[bool, str]:
    """İlan filtreden geçiyor mu? İkinci değer debug logu için Türkçe gerekçe."""
    text = ilan_text(ilan)
    unsure = f.filtre_belirsizse_gonder

    for kw in f.exclude_keywords:
        if contains_keyword(text, kw):
            return False, f"hariç tutulan kelime: {kw!r}"

    if f.include_keywords and not any(contains_keyword(text, kw) for kw in f.include_keywords):
        return False, "aranan kelimelerden hiçbiri yok"

    notes = []
    for label, wanted, have in (
        ("öğrenim", f.education_levels, ilan.education_levels),
        ("KPSS", f.kpss_types, ilan.kpss_types),
    ):
        ok, note = _check_set(label, wanted, have, unsure)
        if not ok:
            return False, note
        if note:
            notes.append(note)

    if f.locations:
        nationwide = any(contains_keyword(text, p) for p in NATIONWIDE_PHRASES)
        if not nationwide:
            ok, note = _check_set("il", f.locations, ilan.locations, unsure)
            if not ok:
                return False, note
            if note:
                notes.append(note)

    return True, "; ".join(notes) or "uygun"


def _check_set(
    label: str, wanted: Iterable[str], have: Iterable[str], unsure: bool
) -> tuple[bool, str]:
    wanted, have = set(wanted), set(have)
    if not wanted:
        return True, ""
    if not have:
        if unsure:
            return True, f"{label} belirsiz → gönderiliyor"
        return False, f"{label} belirsiz → eleniyor"
    if wanted & have:
        return True, ""
    return False, f"{label} uymuyor ({', '.join(sorted(have))})"
