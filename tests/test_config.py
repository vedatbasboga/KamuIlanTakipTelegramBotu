from pathlib import Path

import pytest

from ilanbot.config import ConfigError, load_config, parse_config
from ilanbot.sources import SOURCE_NAMES

ROOT = Path(__file__).resolve().parent.parent


def test_repo_config_is_valid():
    config = load_config(ROOT / "config.yaml")
    assert config.enabled_sources == list(SOURCE_NAMES)
    assert config.filters.education_levels == {"lisans"}
    assert config.filters.kpss_types == {"P3"}
    assert config.filters.locations == frozenset()
    assert "öğretim üyesi" in config.filters.exclude_keywords
    assert config.filters.filtre_belirsizse_gonder is True
    assert config.notify.max_messages_per_run == 15
    assert config.state.prune_after_days == 120


def test_empty_config_uses_defaults(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("", encoding="utf-8")
    config = load_config(path)
    assert config.enabled_sources == list(SOURCE_NAMES)
    assert config.filters.education_levels == frozenset()
    assert config.notify.max_messages_per_run == 15


def test_values_are_normalized():
    config = parse_config(
        {
            "sources": {"iskur": False},
            "filters": {
                "education_levels": ["Lisans", "onlisans"],
                "kpss_types": ["kpss p3", "P93"],
                "locations": ["izmir", "Afyon"],
            },
        }
    )
    assert "iskur" not in config.enabled_sources
    assert config.filters.education_levels == {"lisans", "onlisans"}
    assert config.filters.kpss_types == {"P3", "P93"}
    assert config.filters.locations == {"İZMİR", "AFYONKARAHİSAR"}


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"filtreler": {}}, "bilinmeyen anahtar: filtreler"),
        ({"sources": {"sahibinden": True}}, "bilinmeyen anahtar: sahibinden"),
        ({"sources": {"iskur": "evet"}}, "true ya da false"),
        ({"filters": {"education_levels": "lisans"}}, "bir liste olmalı"),
        ({"filters": {"education_levels": ["ilkokul"]}}, "geçersiz değer: ilkokul"),
        ({"filters": {"kpss_types": ["ALES"]}}, "anlaşılamayan puan türü"),
        ({"filters": {"locations": ["Narnia"]}}, "tanınmayan il"),
        ({"notify": {"max_messages_per_run": 0}}, "pozitif bir tam sayı"),
        ({"notify": {"max_messages_per_run": "15"}}, "pozitif bir tam sayı"),
        ({"state": {"prune_after_days": True}}, "pozitif bir tam sayı"),
        (["liste"], "sözlük"),
    ],
)
def test_invalid_config(raw, fragment):
    with pytest.raises(ConfigError, match=fragment):
        parse_config(raw)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="bulunamadı"):
        load_config(tmp_path / "yok.yaml")


def test_invalid_yaml(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("filters: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="geçerli bir YAML değil"):
        load_config(path)
