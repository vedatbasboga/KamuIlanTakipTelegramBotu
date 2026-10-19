from pathlib import Path

import pytest

from ilanbot.config import ConfigError, load_config, parse_config
from ilanbot.sources import SOURCE_NAMES

ROOT = Path(__file__).resolve().parent.parent


def test_repo_config_is_valid():
    # Değerler kullanıcıya ait; burada sadece dosyanın geçerli olduğu doğrulanır.
    config = load_config(ROOT / "config.yaml")
    assert set(config.sources) == set(SOURCE_NAMES)
    assert config.enabled_sources


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


def test_runners():
    config = parse_config(
        {
            "sources": {"iskur": False},
            "runners": {"github": ["ilan_gov", "iskur"], "local": ["kamuilan_sbb"]},
        }
    )
    assert config.sources_for_runner("github") == ["ilan_gov"]  # iskur kapalı
    assert config.sources_for_runner("local") == ["kamuilan_sbb"]
    with pytest.raises(ConfigError, match="Tanımlı ortamlar: github, local"):
        config.sources_for_runner("bulut")


@pytest.mark.parametrize(
    ("runners", "fragment"),
    [
        ({"github": ["sahibinden"]}, "bilinmeyen kaynak"),
        ({"github": ["iskur"], "local": ["iskur"]}, "tek bir ortamda"),
        ({"github": "iskur"}, "bir liste olmalı"),
        (["github"], "sözlük olmalı"),
    ],
)
def test_invalid_runners(runners, fragment):
    with pytest.raises(ConfigError, match=fragment):
        parse_config({"runners": runners})


def test_repo_config_runners_cover_all_sources():
    config = load_config(ROOT / "config.yaml")
    covered = {name for group in config.runners.values() for name in group}
    assert covered == set(SOURCE_NAMES)
