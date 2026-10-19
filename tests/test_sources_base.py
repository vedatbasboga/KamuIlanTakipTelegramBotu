import pytest

from ilanbot.models import Ilan
from ilanbot.sources import REGISTRY, SOURCE_NAMES
from ilanbot.sources.base import ParseError, parse_rows


def _ilan(i: str) -> Ilan:
    return Ilan(source="s", id=i, title="t", url="https://x")


def test_bad_row_is_skipped(caplog):
    def parse_row(row):
        if row == "bozuk":
            raise ValueError("olmadı")
        return _ilan(row)

    items = parse_rows("s", ["1", "bozuk", "2"], parse_row)
    assert [i.id for i in items] == ["1", "2"]
    assert "2. satır parse edilemedi" in caplog.text


def test_all_rows_broken_raises():
    with pytest.raises(ParseError):
        parse_rows("s", ["a", "b"], lambda row: 1 / 0)


def test_intentionally_skipped_rows_do_not_raise():
    assert parse_rows("s", ["a", "b"], lambda row: None) == []


def test_empty_list_is_not_an_error():
    assert parse_rows("s", [], lambda row: _ilan(row)) == []


def test_duplicates_removed():
    assert len(parse_rows("s", ["1", "1", "2"], _ilan)) == 2


def test_registry():
    assert set(REGISTRY) <= set(SOURCE_NAMES)
    assert "resmi_gazete" not in REGISTRY
    for name, source in REGISTRY.items():
        assert source.name == name
        assert source.display_name
        assert source.min_interval_minutes >= 0
    assert REGISTRY["iskur"].min_interval_minutes == 180
