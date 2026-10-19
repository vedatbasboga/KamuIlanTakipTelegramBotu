"""config.yaml yükleme ve doğrulama."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import EDUCATION_LEVELS, normalize_il, normalize_kpss
from .sources import SOURCE_NAMES
from .text import tr_lower


class ConfigError(Exception):
    """config.yaml geçersiz. Mesaj kullanıcıya olduğu gibi gösterilir."""


@dataclass(frozen=True)
class FiltersConfig:
    education_levels: frozenset[str] = frozenset()
    kpss_types: frozenset[str] = frozenset()
    locations: frozenset[str] = frozenset()
    include_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    filtre_belirsizse_gonder: bool = True


@dataclass(frozen=True)
class NotifyConfig:
    max_messages_per_run: int = 15
    show_deadline_days_left: bool = True


@dataclass(frozen=True)
class StateConfig:
    prune_after_days: int = 120


@dataclass(frozen=True)
class Config:
    sources: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(SOURCE_NAMES, True))
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    state: StateConfig = field(default_factory=StateConfig)
    # Çalışma ortamı adı → o ortamda çalışan kaynaklar (ör. "github", "local").
    runners: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def enabled_sources(self) -> list[str]:
        return [name for name in SOURCE_NAMES if self.sources.get(name)]

    def sources_for_runner(self, runner: str) -> list[str]:
        """Bu ortamda çalışacak, config'te açık kaynaklar."""
        if runner not in self.runners:
            known = ", ".join(sorted(self.runners)) or "(tanımlı ortam yok)"
            raise ConfigError(f"'runners' içinde '{runner}' yok. Tanımlı ortamlar: {known}.")
        group = set(self.runners[runner])
        return [name for name in self.enabled_sources if name in group]


_TOP_KEYS = {"sources", "filters", "notify", "state", "runners"}
_FILTER_KEYS = {
    "education_levels",
    "kpss_types",
    "locations",
    "include_keywords",
    "exclude_keywords",
    "filtre_belirsizse_gonder",
}
_NOTIFY_KEYS = {"max_messages_per_run", "show_deadline_days_left"}
_STATE_KEYS = {"prune_after_days"}


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Config dosyası bulunamadı: {path}") from None
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{path} geçerli bir YAML değil: {e}") from None
    return parse_config(raw if raw is not None else {})


def parse_config(raw: Any) -> Config:
    data = _section(raw, "config", _TOP_KEYS)

    sources_raw = _section(data.get("sources", {}), "sources", set(SOURCE_NAMES))
    sources = dict.fromkeys(SOURCE_NAMES, True)
    for name, value in sources_raw.items():
        sources[name] = _bool(value, f"sources.{name}")

    f = _section(data.get("filters", {}), "filters", _FILTER_KEYS)
    filters = FiltersConfig(
        education_levels=_education(f.get("education_levels")),
        kpss_types=_kpss(f.get("kpss_types")),
        locations=_locations(f.get("locations")),
        include_keywords=_keywords(f.get("include_keywords"), "filters.include_keywords"),
        exclude_keywords=_keywords(f.get("exclude_keywords"), "filters.exclude_keywords"),
        filtre_belirsizse_gonder=_bool(
            f.get("filtre_belirsizse_gonder", True), "filters.filtre_belirsizse_gonder"
        ),
    )

    n = _section(data.get("notify", {}), "notify", _NOTIFY_KEYS)
    notify = NotifyConfig(
        max_messages_per_run=_positive_int(
            n.get("max_messages_per_run", 15), "notify.max_messages_per_run"
        ),
        show_deadline_days_left=_bool(
            n.get("show_deadline_days_left", True), "notify.show_deadline_days_left"
        ),
    )

    s = _section(data.get("state", {}), "state", _STATE_KEYS)
    state = StateConfig(
        prune_after_days=_positive_int(s.get("prune_after_days", 120), "state.prune_after_days")
    )

    return Config(
        sources=sources,
        filters=filters,
        notify=notify,
        state=state,
        runners=_runners(data.get("runners")),
    )


# --- doğrulama yardımcıları -----------------------------------------------------


def _section(value: Any, name: str, allowed: set[str]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"'{name}' bir sözlük (anahtar: değer) olmalı, {_typename(value)} geldi.")
    unknown = sorted(str(k) for k in value if k not in allowed)
    if unknown:
        raise ConfigError(
            f"'{name}' içinde bilinmeyen anahtar: {', '.join(unknown)}. "
            f"Geçerli anahtarlar: {', '.join(sorted(allowed))}."
        )
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"'{name}' true ya da false olmalı, {_typename(value)} geldi.")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"'{name}' pozitif bir tam sayı olmalı, {value!r} geldi.")
    return value


def _str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"'{name}' bir liste olmalı (ör. [a, b]), {_typename(value)} geldi.")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise ConfigError(f"'{name}' listesinde geçersiz değer: {item!r}.")
        out.append(str(item).strip())
    return [item for item in out if item]


def _education(value: Any) -> frozenset[str]:
    name = "filters.education_levels"
    items = [tr_lower(i) for i in _str_list(value, name)]
    bad = [i for i in items if i not in EDUCATION_LEVELS]
    if bad:
        raise ConfigError(
            f"'{name}' içinde geçersiz değer: {', '.join(bad)}. "
            f"Geçerli değerler: {', '.join(sorted(EDUCATION_LEVELS))}."
        )
    return frozenset(items)


def _kpss(value: Any) -> frozenset[str]:
    name = "filters.kpss_types"
    out: set[str] = set()
    for item in _str_list(value, name):
        found = normalize_kpss(item)
        if len(found) != 1:
            raise ConfigError(f"'{name}' içinde anlaşılamayan puan türü: {item!r} (ör. P3, P93).")
        out |= found
    return frozenset(out)


def _locations(value: Any) -> frozenset[str]:
    name = "filters.locations"
    out: set[str] = set()
    for item in _str_list(value, name):
        il = normalize_il(item)
        if il is None:
            raise ConfigError(f"'{name}' içinde tanınmayan il: {item!r}.")
        out.add(il)
    return frozenset(out)


def _runners(value: Any) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"'runners' bir sözlük olmalı, {_typename(value)} geldi.")
    runners: dict[str, tuple[str, ...]] = {}
    owner: dict[str, str] = {}
    for runner, names in value.items():
        items = _str_list(names, f"runners.{runner}")
        for name in items:
            if name not in SOURCE_NAMES:
                raise ConfigError(f"'runners.{runner}' içinde bilinmeyen kaynak: {name!r}.")
            if name in owner:
                raise ConfigError(
                    f"'{name}' hem 'runners.{owner[name]}' hem 'runners.{runner}' içinde; "
                    "bir kaynak tek bir ortamda çalışmalı (aksi halde iki kez bildirilir)."
                )
            owner[name] = str(runner)
        runners[str(runner)] = tuple(items)
    return runners


def _keywords(value: Any, name: str) -> tuple[str, ...]:
    return tuple(_str_list(value, name))


def _typename(value: Any) -> str:
    return {
        "str": "metin",
        "int": "sayı",
        "float": "ondalık sayı",
        "bool": "true/false",
        "list": "liste",
        "dict": "sözlük",
        "NoneType": "boş değer",
    }.get(type(value).__name__, type(value).__name__)
