"""Ortak HTTP istemcisi: anlamlı User-Agent, timeout ve sınırlı retry."""

from __future__ import annotations

import functools
import logging
import ssl
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import certifi
import httpx

from . import __version__

log = logging.getLogger(__name__)

USER_AGENT = (
    f"KamuIlanBot/{__version__} (+https://github.com/vedatbasboga/KamuIlanTakipTelegramBotu)"
)
TIMEOUT_SECONDS = 20.0
RETRY_DELAYS = (1.0, 3.0)  # en fazla 2 retry
_sleep = time.sleep  # testlerde yamalanır


CERTS_DIR = Path(__file__).parent / "certs"


@functools.lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """certifi kök sertifikaları + `certs/` altındaki eksik ara sertifikalar.

    Bazı `.gov.tr` sunucuları (ör. www.ilan.gov.tr) zincirdeki ara sertifikayı göndermiyor;
    tarayıcılar bunu kendisi tamamlar, OpenSSL tamamlamaz. Ara sertifikayı burada eklemek
    doğrulamayı kapatmadan (`verify=False` olmadan) zinciri tamamlar. Kökler yine certifi'den
    gelir; ara sertifikalar yalnızca zincir kurmak için kullanılır.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    for pem in sorted(CERTS_DIR.glob("*.pem")):
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


def make_client(**kwargs: Any) -> httpx.Client:
    """Projenin varsayılanlarıyla bir httpx.Client oluşturur.

    `verify=False` hiçbir yerde kullanılmaz; sertifika sorunları `certs/` ile çözülür.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9"}
    headers.update(kwargs.pop("headers", {}))
    return httpx.Client(
        headers=headers,
        timeout=kwargs.pop("timeout", TIMEOUT_SECONDS),
        verify=kwargs.pop("verify", ssl_context()),
        follow_redirects=True,
        http2=False,
        **kwargs,
    )


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    sleep: Callable[[float], None] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """İsteği atar; 5xx, timeout ve bağlantı hatasında en fazla 2 kez tekrar dener.

    4xx'te tekrar denemez. Başarısız son yanıtta `httpx.HTTPStatusError` fırlatır.
    """
    attempts = len(RETRY_DELAYS) + 1
    for attempt in range(1, attempts + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TransportError as e:  # timeout, bağlantı hatası vb.
            if attempt == attempts:
                raise
            reason = type(e).__name__
        else:
            if response.status_code < 500 or attempt == attempts:
                response.raise_for_status()
                return response
            reason = f"HTTP {response.status_code}"
        delay = RETRY_DELAYS[attempt - 1]
        log.warning(
            "%s %s: %s, %.0f sn sonra tekrar denenecek (%d/%d)",
            method,
            url,
            reason,
            delay,
            attempt,
            len(RETRY_DELAYS),
        )
        (sleep or _sleep)(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def get_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    return request_with_retry(client, "GET", url, **kwargs)
