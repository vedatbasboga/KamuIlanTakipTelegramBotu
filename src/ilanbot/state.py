"""data/state.json yükleme, kaydetme ve budama.

State bot tarafından yönetilir; elle düzenlenmez (test amaçlı `seen` silme hariç).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import now as _now

STATE_VERSION = 1


class StateError(Exception):
    """state.json okunamadı ya da bozuk."""


@dataclass
class SourceHealth:
    bootstrapped: bool = False
    consecutive_failures: int = 0
    last_success: str | None = None
    last_count: int | None = None
    warned: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceHealth:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Stats:
    """Son haftalık rapordan bu yana sayaçlar."""

    scanned: int = 0
    sent: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stats:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class State:
    seen: dict[str, str] = field(default_factory=dict)  # ilan.key → ISO 8601 zaman
    sources: dict[str, SourceHealth] = field(default_factory=dict)
    last_heartbeat: str | None = None
    stats: Stats = field(default_factory=Stats)
    # Bu sürümün tanımadığı üst düzey anahtarlar; kaybolmasın diye aynen geri yazılır.
    extra: dict[str, Any] = field(default_factory=dict)

    def health(self, source: str) -> SourceHealth:
        """Kaynağın sağlık kaydını döndürür, yoksa oluşturur."""
        return self.sources.setdefault(source, SourceHealth())

    def mark_seen(self, key: str, when: datetime | None = None) -> None:
        self.seen[key] = (when or _now()).isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extra,
            "version": STATE_VERSION,
            "seen": dict(self.seen),
            "sources": {name: asdict(h) for name, h in self.sources.items()},
            "last_heartbeat": self.last_heartbeat,
            "stats": asdict(self.stats),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> State:
        version = data.get("version", STATE_VERSION)
        if version != STATE_VERSION:
            raise StateError(f"Desteklenmeyen state sürümü: {version} (beklenen {STATE_VERSION})")
        extra = {
            k: v
            for k, v in data.items()
            if k not in {"version", "seen", "sources", "last_heartbeat", "stats"}
        }
        return cls(
            seen=dict(data.get("seen") or {}),
            sources={
                name: SourceHealth.from_dict(h) for name, h in (data.get("sources") or {}).items()
            },
            last_heartbeat=data.get("last_heartbeat"),
            stats=Stats.from_dict(data.get("stats") or {}),
            extra=extra,
        )


def load_state(path: str | Path) -> State:
    """State'i yükler. Dosya yoksa boş state döner.

    Dosya bozuksa hata fırlatır: Bozuk state'i sessizce boş saymak, tüm kaynakların
    yeniden "ilk çalışma" sayılması ve ilanların kaçması demektir.
    """
    path = Path(path)
    if not path.exists():
        return State()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise StateError(f"{path} okunamadı: {e}") from e
    if not isinstance(data, dict):
        raise StateError(f"{path} beklenen biçimde değil (JSON nesnesi olmalı).")
    return State.from_dict(data)


def save_state(path: str | Path, state: State) -> None:
    """State'i atomik olarak yazar (geçici dosya + os.replace).

    Anahtarlar sıralı ve girintili yazılır ki git diff'leri okunabilir olsun.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def prune(state: State, days: int, now: datetime | None = None) -> int:
    """`seen` içinden `days` günden eski kayıtları siler, silinen sayısını döndürür.

    Zamanı okunamayan kayıtlar silinmez (silinirse ilan yeniden bildirilebilir).
    """
    cutoff = (now or _now()) - timedelta(days=days)
    old = []
    for key, stamp in state.seen.items():
        try:
            seen_at = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if seen_at.tzinfo is not None and seen_at < cutoff:
            old.append(key)
    for key in old:
        del state.seen[key]
    return len(old)
