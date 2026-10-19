from datetime import datetime, timezone

import pytest

from ilanbot.dates import month_number, parse_iso, parse_tr_date
from ilanbot.models import TZ


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("28.10.2026", datetime(2026, 10, 28, tzinfo=TZ)),
        ("28/10/2026 17:00", datetime(2026, 10, 28, 17, 0, tzinfo=TZ)),
        ("23.10.2026 17:00 ", datetime(2026, 10, 23, 17, 0, tzinfo=TZ)),
        ("19.10.2026 00:00:00", datetime(2026, 10, 19, tzinfo=TZ)),
        ("28 Ekim 2026", datetime(2026, 10, 28, tzinfo=TZ)),
        ("16 Ekim 2026", datetime(2026, 10, 16, tzinfo=TZ)),
        ("1 ŞUBAT 2027", datetime(2027, 2, 1, tzinfo=TZ)),
        ("3 ağustos 2026 14:30", datetime(2026, 8, 3, 14, 30, tzinfo=TZ)),
        ("Son başvuru: 02.11.2026 tarihine kadar", datetime(2026, 11, 2, tzinfo=TZ)),
        ("2026-10-19T17:00:00", datetime(2026, 10, 19, 17, 0, tzinfo=TZ)),
    ],
)
def test_parse_tr_date(text, expected):
    result = parse_tr_date(text)
    assert result == expected
    assert result.tzinfo is not None


def test_parse_tr_date_default_year():
    assert parse_tr_date("2 Kasım", default_year=2026) == datetime(2026, 11, 2, tzinfo=TZ)
    assert parse_tr_date("2 Kasım") is None


@pytest.mark.parametrize("text", [None, "", "tarih yok", "32.13.2026", "5 ilan"])
def test_parse_tr_date_none(text):
    assert parse_tr_date(text) is None


def test_parse_iso_utc_is_converted():
    dt = parse_iso("2026-10-18T21:00:01Z")
    assert dt == datetime(2026, 10, 18, 21, 0, 1, tzinfo=timezone.utc)
    assert (dt.day, dt.hour) == (19, 0)  # İstanbul'da ertesi gün 00:00


def test_parse_iso_fraction_and_naive():
    assert parse_iso("2026-10-12T13:36:22.91") == datetime(2026, 10, 12, 13, 36, 22, 910000, TZ)
    assert parse_iso("bozuk") is None
    assert parse_iso(None) is None


@pytest.mark.parametrize(
    ("name", "num"), [("Ekim", 10), ("KASIM", 11), ("Ağustos", 8), ("agustos", 8), ("Ara.", 12)]
)
def test_month_number(name, num):
    assert month_number(name) == num
