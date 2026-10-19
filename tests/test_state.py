import json
import os
from datetime import datetime, timedelta

import pytest

from ilanbot.models import TZ
from ilanbot.state import State, StateError, load_state, prune, save_state


def test_load_missing_returns_empty(tmp_path):
    state = load_state(tmp_path / "yok.json")
    assert state.seen == {}
    assert state.sources == {}
    assert state.last_heartbeat is None


def test_roundtrip(tmp_path):
    path = tmp_path / "data" / "state.json"  # klasör yoksa oluşturulmalı
    state = State()
    state.mark_seen("kamuilan_sbb:1", datetime(2026, 10, 19, 12, 0, tzinfo=TZ))
    h = state.health("kamuilan_sbb")
    h.bootstrapped = True
    h.last_count = 214
    save_state(path, state)

    loaded = load_state(path)
    assert loaded.seen == {"kamuilan_sbb:1": "2026-10-19T12:00:00+03:00"}
    assert loaded.sources["kamuilan_sbb"].bootstrapped is True
    assert loaded.sources["kamuilan_sbb"].last_count == 214
    assert loaded.sources["kamuilan_sbb"].consecutive_failures == 0


def test_saved_format_is_diff_friendly(tmp_path):
    path = tmp_path / "state.json"
    state = State()
    state.mark_seen("b:2", datetime(2026, 1, 1, tzinfo=TZ))
    state.mark_seen("a:1", datetime(2026, 1, 1, tzinfo=TZ))
    save_state(path, state)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["version"] == 1
    assert list(data["seen"]) == ["a:1", "b:2"]  # sıralı
    assert text.endswith("\n")
    assert '\n  "seen": {\n' in text  # indent=2


def test_unknown_keys_preserved(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps({"version": 1, "seen": {}, "sources": {}, "gelecek_alan": [1, 2]}),
        encoding="utf-8",
    )
    save_state(path, load_state(path))
    assert json.loads(path.read_text(encoding="utf-8"))["gelecek_alan"] == [1, 2]


def test_atomic_write_keeps_old_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    state = State()
    state.mark_seen("x:1")
    save_state(path, state)
    before = path.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk dolu")

    monkeypatch.setattr(os, "replace", boom)
    state.mark_seen("x:2")
    with pytest.raises(OSError):
        save_state(path, state)

    assert path.read_text(encoding="utf-8") == before
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]  # geçici dosya kalmadı


def test_corrupt_file_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(StateError):
        load_state(path)


def test_wrong_version_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(StateError):
        load_state(path)


def test_prune():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=TZ)
    state = State()
    state.mark_seen("eski", now - timedelta(days=121))
    state.mark_seen("sinirda", now - timedelta(days=119))
    state.mark_seen("yeni", now)
    state.seen["bozuk"] = "dün"

    removed = prune(state, 120, now=now)

    assert removed == 1
    assert set(state.seen) == {"sinirda", "yeni", "bozuk"}
