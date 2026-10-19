"""Orkestrasyon: kaynakları çalıştır → yenileri bul → filtrele → gönder → state'i güncelle."""

from __future__ import annotations

import difflib
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from .config import Config
from .filters import matches
from .models import Ilan
from .models import now as _now
from .notifier import format_digest, format_ilan, source_label
from .sources import SOURCE_NAMES, Source
from .state import SourceHealth, State
from .text import tr_lower

log = logging.getLogger(__name__)

MAX_ENRICH_PER_SOURCE = 20  # çalışma başına kaynak başına en fazla detay isteği
FAILURE_WARN_THRESHOLD = 6  # ≈ 3 saat (30 dk aralıkla)
ZERO_SUSPICION_MIN = 10  # önceden ≥10 ilan dönen kaynak 0 dönerse hata sayılır
DUPLICATE_RATIO = 0.9

# Mesaj gönderen fonksiyon: True = iletildi. Dry-run'da konsola yazar.
Deliver = Callable[[str], bool]


@dataclass
class RunSummary:
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    sent: list[Ilan] = field(default_factory=list)

    @property
    def ran(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def all_failed(self) -> bool:
        return self.ran > 0 and not self.succeeded


@dataclass
class Candidate:
    """Gönderilecek ilan + başka kaynaklarda görülen aynı ilan(lar)."""

    ilan: Ilan
    twins: list[Ilan] = field(default_factory=list)

    @property
    def also_in(self) -> list[str]:
        return list(dict.fromkeys(t.source for t in self.twins))

    @property
    def keys(self) -> list[str]:
        return [self.ilan.key] + [t.key for t in self.twins]


def run(
    sources: list[Source],
    config: Config,
    state: State,
    client: httpx.Client,
    deliver: Deliver,
    now: datetime | None = None,
    *,
    admin_deliver: Deliver | None = None,
    label: str | None = None,
) -> RunSummary:
    """Bir çalışma turu.

    `deliver` ilan bildirimlerini (kanal), `admin_deliver` bakım mesajlarını (sağlık uyarısı,
    haftalık rapor) gönderir; verilmezse bakım mesajları da `deliver`'a gider. `label` haftalık
    raporda hangi ortamın (ör. "github", "local") konuştuğunu belirtir.
    """
    now = now or _now()
    admin = admin_deliver or deliver
    summary = RunSummary()
    to_send: list[Ilan] = []
    scanned = 0

    for source in sources:
        health = state.health(source.name)
        if _too_soon(source, health, now):
            summary.skipped.append(source.name)
            log.info(
                "[%s] atlandı (en fazla %d dakikada bir)", source.name, source.min_interval_minutes
            )
            continue
        started = time.monotonic()
        try:
            items = source.list_items(client)
            if not items and (health.last_count or 0) >= ZERO_SUSPICION_MIN:
                raise RuntimeError(
                    f"0 ilan döndü (önceki: {health.last_count}); site yapısı değişmiş olabilir"
                )
        except Exception as e:  # bir kaynağın hatası diğerlerini durdurmaz
            summary.failed.append(source.name)
            _record_failure(source, health, e, admin)
            continue

        new = [i for i in items if i.key not in state.seen]
        if not health.bootstrapped:  # kural 4: sessiz ilk çalışma
            for ilan in items:
                state.mark_seen(ilan.key, now)
            health.bootstrapped = True
            _record_success(source, health, len(items), now, admin)
            summary.succeeded.append(source.name)
            log.info("[%s] ilk çalışma: %d ilan sessizce kaydedildi", source.name, len(items))
            continue

        if len(new) > MAX_ENRICH_PER_SOURCE:
            log.info(
                "[%s] %d yeni ilanın %d tanesi işlendi, kalanı sonraki çalışmada",
                source.name,
                len(new),
                MAX_ENRICH_PER_SOURCE,
            )
            new = new[:MAX_ENRICH_PER_SOURCE]
        new = [_enrich(source, client, ilan) for ilan in new]

        passed = 0
        for ilan in new:
            state.mark_seen(ilan.key, now)  # filtreden geçmeyen de görüldü sayılır
            ok, reason = matches(ilan, config.filters)
            log.debug(
                "[%s] %s: %s → %s", source.name, ilan.title, "geçti" if ok else "elendi", reason
            )
            if ok:
                to_send.append(ilan)
                passed += 1

        _record_success(source, health, len(items), now, admin)
        summary.succeeded.append(source.name)
        scanned += len(items)
        log.info(
            "[%s] %d ilan, %d yeni, %d filtreden geçti (%.1f sn)",
            source.name,
            len(items),
            len(new),
            passed,
            time.monotonic() - started,
        )

    candidates = merge_duplicates(to_send)
    candidates.sort(key=lambda c: _deadline_key(c.ilan))
    summary.sent = _send(candidates, config, state, now, deliver)
    log.info(
        "%d kaynak çalıştı (%d başarılı, %d hatalı, %d atlandı). Toplam: %d bildirim gönderildi",
        summary.ran,
        len(summary.succeeded),
        len(summary.failed),
        len(summary.skipped),
        len(summary.sent),
    )
    state.stats.scanned += scanned
    state.stats.sent += len(summary.sent)
    maybe_heartbeat(sources, state, now, admin, label)
    return summary


# --- haftalık rapor -----------------------------------------------------------------------

HEARTBEAT_WEEKDAY = 6  # Pazar
HEARTBEAT_HOUR = 20
HEARTBEAT_MIN_GAP = timedelta(days=6)
HEARTBEAT_MAX_GAP = timedelta(days=8)  # Pazar akşamı kaçırılırsa (bilgisayar kapalı) yine gönder

RUNNER_LABELS = {"github": "GitHub", "local": "bilgisayar"}


def heartbeat_due(last: str | None, now: datetime) -> bool:
    """Pazar 20:00'den sonra ve son rapordan ≥6 gün geçtiyse; ya da ≥8 gün geçtiyse her zaman."""
    try:
        gap = now - datetime.fromisoformat(last) if last else None
    except ValueError:
        gap = None
    if gap is not None and gap >= HEARTBEAT_MAX_GAP:
        return True
    sunday_evening = now.weekday() == HEARTBEAT_WEEKDAY and now.hour >= HEARTBEAT_HOUR
    return sunday_evening and (gap is None or gap >= HEARTBEAT_MIN_GAP)


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")  # 1284 → "1.284"


def format_heartbeat(sources: list[Source], state: State, label: str | None) -> str:
    where = f" ({RUNNER_LABELS.get(label, label)})" if label else ""
    lines = [
        f"💚 <b>Kamu İlan Botu çalışıyor</b>{where}",
        f"Son rapordan beri: {_thousands(state.stats.scanned)} ilan tarandı, "
        f"{_thousands(state.stats.sent)} bildirim gönderildi",
    ]
    for source in sources:
        h = state.health(source.name)
        if h.consecutive_failures:
            status = f"⚠️ {source_label(source.name)} (art arda {h.consecutive_failures} hata)"
        else:
            status = f"✅ {source_label(source.name)}"
        lines.append(status)
    return "\n".join(lines)


def maybe_heartbeat(
    sources: list[Source], state: State, now: datetime, admin: Deliver, label: str | None
) -> None:
    if not sources or not heartbeat_due(state.last_heartbeat, now):
        return
    if admin(format_heartbeat(sources, state, label)):
        state.last_heartbeat = now.isoformat(timespec="seconds")
        state.stats.scanned = state.stats.sent = 0
        log.info("Haftalık rapor gönderildi")


# --- kaynak yardımcıları -----------------------------------------------------------------


def _too_soon(source: Source, health: SourceHealth, now: datetime) -> bool:
    minutes = getattr(source, "min_interval_minutes", 0)
    if not minutes or not health.last_success or not health.bootstrapped:
        return False
    try:
        last = datetime.fromisoformat(health.last_success)
    except ValueError:
        return False
    # Cron birkaç dakika kayabildiği için 5 dk tolerans.
    return now - last < timedelta(minutes=minutes - 5)


def _enrich(source: Source, client: httpx.Client, ilan: Ilan) -> Ilan:
    try:
        return source.enrich(client, ilan)
    except Exception as e:  # detay alınamazsa ilan listedeki bilgilerle devam eder
        log.warning("[%s] detay alınamadı (%s): %s: %s", source.name, ilan.id, type(e).__name__, e)
        return ilan


def _record_failure(
    source: Source, health: SourceHealth, error: Exception, deliver: Deliver
) -> None:
    health.consecutive_failures += 1
    log.error(
        "[%s] HATA: %s: %s (art arda %d.)",
        source.name,
        type(error).__name__,
        error,
        health.consecutive_failures,
    )
    if health.consecutive_failures >= FAILURE_WARN_THRESHOLD and not health.warned:
        last = _format_stamp(health.last_success)
        text = (
            f"⚠️ <b>{source_label(source.name)}</b> art arda {health.consecutive_failures} kez "
            f"okunamadı.\nSon başarılı: {last}\nHata: {type(error).__name__}"
        )
        health.warned = deliver(text)


def _record_success(
    source: Source, health: SourceHealth, count: int, now: datetime, deliver: Deliver
) -> None:
    if health.warned:
        deliver(f"✅ <b>{source_label(source.name)}</b> tekrar çalışıyor.")
        health.warned = False
    health.consecutive_failures = 0
    health.last_success = now.isoformat(timespec="seconds")
    health.last_count = count


def _format_stamp(stamp: str | None) -> str:
    if not stamp:
        return "hiç"
    try:
        return f"{datetime.fromisoformat(stamp):%d.%m.%Y %H:%M}"
    except ValueError:
        return stamp


# --- kaynaklar arası tekrar ve gönderim ----------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]")


def _dedup_key(ilan: Ilan) -> str:
    text = tr_lower(f"{ilan.institution or ''} {ilan.title}")
    return " ".join(_PUNCT_RE.sub(" ", text).split())


def merge_duplicates(ilanlar: list[Ilan]) -> list[Candidate]:
    """Farklı kaynaklardan gelen aynı ilanı (kurum+başlık benzerliği ≥0.9) tek adaya indirir.

    Kaynak önceliği `SOURCE_NAMES` sırasıdır; diğer kaynaklar "ayrıca:" notu olur. Aynı kaynağın
    iki ilanı hiçbir zaman birleştirilmez (ör. aynı kurumun iki farklı alımı).
    """
    order = {name: i for i, name in enumerate(SOURCE_NAMES)}
    ordered = sorted(ilanlar, key=lambda i: order.get(i.source, len(order)))
    result: list[Candidate] = []
    keys: list[str] = []
    for ilan in ordered:
        key = _dedup_key(ilan)
        for cand, cand_key in zip(result, keys, strict=True):
            if ilan.source in {cand.ilan.source, *cand.also_in}:
                continue
            if difflib.SequenceMatcher(None, key, cand_key).ratio() >= DUPLICATE_RATIO:
                cand.twins.append(ilan)
                break
        else:
            result.append(Candidate(ilan))
            keys.append(key)
    return result


def _deadline_key(ilan: Ilan) -> tuple[bool, float]:
    """Son başvurusu en yakın olan önce; tarihi bilinmeyenler en sonda."""
    return (ilan.deadline is None, ilan.deadline.timestamp() if ilan.deadline else 0.0)


def _send(
    candidates: list[Candidate], config: Config, state: State, now: datetime, deliver: Deliver
) -> list[Ilan]:
    """Adayları gönderir. İletilemeyenler `seen`'den geri alınır ki sonraki çalışmada denensin."""
    if not candidates:
        return []
    show_days = config.notify.show_deadline_days_left
    if len(candidates) > config.notify.max_messages_per_run:
        batches = [(format_digest([c.ilan for c in candidates], now), candidates)]
    else:
        batches = [
            (format_ilan(c.ilan, now, show_days_left=show_days, also_in=c.also_in), [c])
            for c in candidates
        ]

    sent: list[Ilan] = []
    for text, batch in batches:
        if deliver(text):
            sent += [c.ilan for c in batch]
            continue
        for c in batch:  # gönderilmeyen ilan kaybolmasın (en kötü sonuç budur)
            for key in c.keys:
                state.seen.pop(key, None)
        log.error("%d ilan gönderilemedi; sonraki çalışmada tekrar denenecek", len(batch))
    return sent
