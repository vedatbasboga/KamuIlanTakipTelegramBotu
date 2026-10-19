"""Türkçe tarih ayrıştırma."""

from __future__ import annotations

import re
from datetime import datetime

from .models import TZ
from .text import ascii_fold, tr_lower

# ascii_fold(tr_lower(ad)) → ay numarası. Kısaltmalar da kabul edilir.
_MONTHS = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}
_MONTH_ABBR = {name[:3]: num for name, num in _MONTHS.items()}

_NUMERIC_RE = re.compile(
    r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:\s+(\d{1,2})[:.](\d{2})(?::(\d{2}))?)?(?!\d)"
)
_ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_FRACTION_RE = re.compile(r"\.(\d+)")
_WORDS_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s+([^\W\d_]+)\.?(?:\s+(\d{4}))?(?:\s+(\d{1,2})[:.](\d{2}))?"
)


def month_number(name: str) -> int | None:
    key = ascii_fold(tr_lower(name.strip().rstrip(".")))
    return _MONTHS.get(key) or (_MONTH_ABBR.get(key) if len(key) == 3 else None)


def to_tz(dt: datetime) -> datetime:
    """Naive datetime'ı Europe/Istanbul kabul eder; tz'li olanı Europe/Istanbul'a çevirir."""
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)


def parse_iso(text: str | None) -> datetime | None:
    """ISO 8601 ("2026-10-18T21:00:01Z", "2026-10-19T17:00:00") → Europe/Istanbul."""
    if not text:
        return None
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # Python 3.10 fromisoformat kesirli saniyeyi sadece 3 ya da 6 hane kabul eder.
    text = _FRACTION_RE.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), text)
    try:
        return to_tz(datetime.fromisoformat(text))
    except ValueError:
        return None


def parse_tr_date(text: str | None, *, default_year: int | None = None) -> datetime | None:
    """Metindeki ilk tarihi Europe/Istanbul timezone'lu datetime olarak döndürür.

    Desteklenen biçimler: "28.10.2026", "28/10/2026 17:00", "28 Ekim 2026", "28 Ekim"
    (`default_year` ile), "2026-10-28T17:00:00Z". Saat yoksa 00:00 kabul edilir.
    """
    if not text:
        return None
    if m := _ISO_RE.search(text):
        if dt := parse_iso(m.group(0)):
            return dt
    if m := _NUMERIC_RE.search(text):
        d, mo, y, hh, mm, ss = m.groups()
        return _build(int(y), int(mo), int(d), hh, mm, ss)
    for m in _WORDS_RE.finditer(text):
        d, month_name, y, hh, mm = m.groups()
        mo = month_number(month_name)
        if mo is None:
            continue
        year = int(y) if y else default_year
        if year is None:
            continue
        return _build(year, mo, int(d), hh, mm, None)
    return None


def _build(
    year: int, month: int, day: int, hh: str | None, mm: str | None, ss: str | None
) -> datetime | None:
    try:
        return datetime(year, month, day, int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=TZ)
    except ValueError:
        return None
