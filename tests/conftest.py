import json
from datetime import datetime
from pathlib import Path

import pytest

from ilanbot.models import TZ

FIXTURES = Path(__file__).parent / "fixtures"

# Fixture'ların kaydedildiği an; "bugün"e göre çalışan parser'lar bununla test edilir.
FIXTURE_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=TZ)


def fixture_text(rel: str) -> str:
    return (FIXTURES / rel).read_text(encoding="utf-8")


def fixture_json(rel: str):
    return json.loads(fixture_text(rel))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Retry beklemeleri testleri yavaşlatmasın."""
    monkeypatch.setattr("ilanbot.http._sleep", lambda _: None)
