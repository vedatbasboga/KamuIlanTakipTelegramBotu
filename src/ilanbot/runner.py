"""Orkestrasyon: kaynakları çalıştır → yenileri bul → filtrele → gönder → state'i güncelle.

Aşama 1'de sadece iskelet: kaynakları çalıştırır, sağlık kaydını günceller, özet döner.
Dedup, filtre ve gönderim Aşama 5'te eklenecek.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from .config import Config
from .models import Ilan
from .models import now as _now
from .sources import Source
from .state import State

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    to_send: list[Ilan] = field(default_factory=list)

    @property
    def ran(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def all_failed(self) -> bool:
        return self.ran > 0 and not self.succeeded


def run(
    sources: list[Source],
    config: Config,
    state: State,
    client: httpx.Client,
) -> RunSummary:
    summary = RunSummary()
    for source in sources:
        health = state.health(source.name)
        started = time.monotonic()
        try:
            items = source.list_items(client)
        except Exception as e:  # kaynaklar birbirinden yalıtılmış (CLAUDE.md kural 2)
            health.consecutive_failures += 1
            summary.failed.append(source.name)
            log.error(
                "[%s] HATA: %s: %s (art arda %d.)",
                source.name,
                type(e).__name__,
                e,
                health.consecutive_failures,
            )
            continue
        health.consecutive_failures = 0
        health.last_success = _now().isoformat(timespec="seconds")
        health.last_count = len(items)
        summary.succeeded.append(source.name)
        log.info("[%s] %d ilan (%.1f sn)", source.name, len(items), time.monotonic() - started)
        for ilan in items[:5]:
            deadline = f" (son: {ilan.deadline:%d.%m.%Y})" if ilan.deadline else ""
            who = f"{ilan.institution} — " if ilan.institution else ""
            log.debug("    • %s%s%s", who, ilan.title, deadline)

    log.info(
        "%d kaynak çalıştı: %d başarılı, %d hatalı",
        summary.ran,
        len(summary.succeeded),
        len(summary.failed),
    )
    return summary
