"""Ortak HTTP istemcisi: anlamlı User-Agent, timeout ve sınırlı retry."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from . import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"KamuIlanBot/{__version__} (+https://github.com/vedatbasboga/KamuIlanTakipTelegramBotu)"
TIMEOUT_SECONDS = 20.0
RETRY_DELAYS = (1.0, 3.0)  # en fazla 2 retry


def make_client(**kwargs: Any) -> httpx.Client:
    """Projenin varsayılanlarıyla bir httpx.Client oluşturur.

    `verify=False` varsayılan değildir. Bir kaynağın sertifika zinciri sorunluysa,
    o kaynakta açıkça ve gerekçesiyle ayrı bir client kullanılmalı.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9"}
    headers.update(kwargs.pop("headers", {}))
    return httpx.Client(
        headers=headers,
        timeout=kwargs.pop("timeout", TIMEOUT_SECONDS),
        follow_redirects=True,
        http2=False,
        **kwargs,
    )


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
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
        sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def get_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    return request_with_retry(client, "GET", url, **kwargs)
