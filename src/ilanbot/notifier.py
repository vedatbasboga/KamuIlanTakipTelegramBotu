"""Telegram bildirimi: mesaj biçimlendirme ve Bot API `sendMessage` ile gönderim.

Token hiçbir log satırında görünmez: httpx'in istek logları ve hata mesajları maskelenir.
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
from collections.abc import Callable, Iterable
from datetime import datetime

import httpx

from .models import Ilan
from .sources import DISPLAY_NAMES, SOURCE_NAMES

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LEN = 4096
MIN_INTERVAL_SECONDS = 1.0  # aynı sohbete art arda gönderim sınırı
DEADLINE_WARN_DAYS = 3

_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")


def mask_token(text: str) -> str:
    """Metindeki `bot<id>:<gizli>` kalıbını `bot***` ile değiştirir."""
    return _TOKEN_RE.sub("bot***", text)


class _RedactTokenFilter(logging.Filter):
    """httpx'in "HTTP Request: POST https://api.telegram.org/bot<TOKEN>/..." logunu maskeler."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = mask_token(message)
        if masked != message:
            record.msg, record.args = masked, None
        return True


logging.getLogger("httpx").addFilter(_RedactTokenFilter())


# --- Biçimlendirme (saf fonksiyonlar) --------------------------------------------

EDUCATION_LABELS = {
    "ortaogretim": "Ortaöğretim",
    "onlisans": "Ön Lisans",
    "lisans": "Lisans",
    "yuksek_lisans": "Yüksek Lisans",
    "doktora": "Doktora",
}
MAX_LOCATIONS_SHOWN = 3


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _kpss_sort_key(code: str) -> tuple[int, str]:
    digits = code[1:]
    return (int(digits), code) if digits.isdigit() else (10**6, code)


def _deadline_line(deadline: datetime, now: datetime, show_days_left: bool) -> str:
    days = (deadline.date() - now.date()).days
    icon = "⚠️" if days <= DEADLINE_WARN_DAYS else "⏳"
    line = f"{icon} Son başvuru: {deadline:%d.%m.%Y}"
    if show_days_left:
        if days < 0:
            line += " (süresi doldu)"
        elif days == 0:
            line += " (bugün son gün)"
        elif days == 1:
            line += " (yarın son gün)"
        else:
            line += f" ({days} gün kaldı)"
    return line


def source_label(source: str) -> str:
    return DISPLAY_NAMES.get(source, source)


def format_ilan(
    ilan: Ilan,
    now: datetime,
    *,
    show_days_left: bool = True,
    also_in: Iterable[str] = (),
) -> str:
    """Tek ilan kartı (Telegram HTML). Boş alanların satırı/öğesi gösterilmez.

    `also_in`: Aynı ilanın görüldüğü diğer kaynaklar (kaynaklar arası tekrar önleme).
    """
    lines: list[str] = []
    if ilan.institution:
        lines += [f"🆕 <b>{_e(ilan.institution)}</b>", _e(ilan.title)]
    else:
        lines.append(f"🆕 <b>{_e(ilan.title)}</b>")

    tags = []
    if ilan.education_levels:
        levels = [
            label for code, label in EDUCATION_LABELS.items() if code in ilan.education_levels
        ]
        tags.append("🎓 " + ", ".join(levels))
    if ilan.kpss_types:
        tags.append("📊 KPSS " + ", ".join(sorted(ilan.kpss_types, key=_kpss_sort_key)))
    if ilan.locations:
        locs = sorted(ilan.locations)
        shown = ", ".join(locs[:MAX_LOCATIONS_SHOWN])
        if len(locs) > MAX_LOCATIONS_SHOWN:
            shown += f" +{len(locs) - MAX_LOCATIONS_SHOWN} il"
        tags.append("📍 " + _e(shown))

    details = []
    if tags:
        details.append(" · ".join(tags))
    if ilan.position_count:
        details.append(f"👥 {ilan.position_count} kadro")
    if ilan.deadline:
        details.append(_deadline_line(ilan.deadline, now, show_days_left))
    if details:
        lines += ["", *details]

    footer = f'🔗 <a href="{_e(ilan.url)}">İlana git</a> · <i>{_e(source_label(ilan.source))}</i>'
    others = [source_label(s) for s in also_in]
    if others:
        footer += f"\n<i>ayrıca: {_e(', '.join(others))}</i>"
    lines += ["", footer]
    return "\n".join(lines)


def format_digest(ilanlar: list[Ilan], now: datetime) -> str:
    """Çok sayıda ilan için özet mesaj; kaynağa göre gruplanmış.

    Her satır kendi içinde kapalı HTML'dir, böylece `split_message` satır sınırından güvenle böler.
    """
    order = {name: i for i, name in enumerate(SOURCE_NAMES)}
    groups: dict[str, list[Ilan]] = {}
    for ilan in ilanlar:
        groups.setdefault(ilan.source, []).append(ilan)

    lines = [f"📋 <b>{len(ilanlar)} yeni ilan</b>"]
    for source in sorted(groups, key=lambda s: (order.get(s, len(order)), s)):
        lines += ["", f"<b>{_e(source_label(source))}</b>"]
        for ilan in groups[source]:
            link = f'<a href="{_e(ilan.url)}">{_e(ilan.title)}</a>'
            line = f"• {_e(ilan.institution)} — {link}" if ilan.institution else f"• {link}"
            if ilan.deadline:
                line += f" <i>(son: {ilan.deadline:%d.%m})</i>"
            lines.append(line)
    return "\n".join(lines)


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Metni satır sınırlarından `limit` karakteri aşmayan parçalara böler."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # tek satır sınırı aşıyorsa mecburen kes
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current.strip():
        chunks.append(current)
    return chunks


# --- Gönderim ---------------------------------------------------------------------


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        client: httpx.Client,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = f"{API_BASE}/bot{token}/sendMessage"
        self._token = token
        self.chat_id = chat_id
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._last_sent: float | None = None

    def send(self, text: str) -> bool:
        """Mesajı gönderir (gerekirse parçalara bölerek). Tüm parçalar gittiyse True."""
        return all(self._send_chunk(chunk) for chunk in split_message(text))

    def _send_chunk(self, text: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        for attempt in (1, 2):
            self._throttle()
            try:
                response = self._client.post(self._url, json=payload)
            except httpx.HTTPError as e:
                log.error("Telegram gönderim hatası: %s: %s", type(e).__name__, self._mask(str(e)))
                return False
            finally:
                self._last_sent = self._clock()

            if response.status_code == 429 and attempt == 1:
                wait = self._retry_after(response)
                log.warning("Telegram hız sınırı (429), %s sn bekleniyor.", wait)
                self._sleep(wait)
                continue
            if response.is_success:
                return True
            log.error(
                "Telegram gönderimi başarısız: HTTP %d %s",
                response.status_code,
                self._mask(self._description(response)),
            )
            return False
        return False

    def _throttle(self) -> None:
        if self._last_sent is None:
            return
        elapsed = self._clock() - self._last_sent
        if elapsed < MIN_INTERVAL_SECONDS:
            self._sleep(MIN_INTERVAL_SECONDS - elapsed)

    def _mask(self, text: str) -> str:
        return mask_token(text).replace(self._token, "***")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        try:
            return float(response.json()["parameters"]["retry_after"])
        except (ValueError, KeyError, TypeError):
            return 5.0

    @staticmethod
    def _description(response: httpx.Response) -> str:
        try:
            return str(response.json().get("description", ""))
        except ValueError:
            return response.text[:200]


class NotifierConfigError(Exception):
    pass


def notifier_from_env(client: httpx.Client) -> TelegramNotifier:
    """TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenlerinden notifier oluşturur."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [
        name
        for name, value in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id))
        if not value
    ]
    if missing:
        raise NotifierConfigError(
            f"Ortam değişkeni eksik: {', '.join(missing)} (.env dosyasını ya da GitHub secrets'ı "
            "kontrol et)."
        )
    return TelegramNotifier(token, chat_id, client)
