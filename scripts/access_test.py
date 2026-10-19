"""Kaynaklara erişim testi (Aşama 6.1).

GitHub runner'ları yurt dışı IP'lerden çalışır; bazı .gov.tr siteleri bunları engelleyebilir.
Her kaynağın liste uç noktasına bir istek atar, durum kodu / boyut / süre / engel işaretlerini ve
yanıtın parse edilip edilemediğini ölçer. Sonuç tablo olarak konsola ve (varsa)
$GITHUB_STEP_SUMMARY'ye yazılır.

Kullanım: PYTHONPATH=src python scripts/access_test.py
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from ilanbot.http import make_client
from ilanbot.sources import ilan_gov, iskur, kamuilan_sbb, kariyer_kapisi, yerel_yonetimler

# Engel/challenge sayfalarına özgü ifadeler. Genel kelimeler ("cloudflare" gibi) kullanılmaz:
# İŞKUR sayfası cdnjs.cloudflare.com'dan JS yüklediği için yanlış alarm verir.
BLOCK_MARKERS = (
    "captcha",
    "cf-chl",
    "just a moment...",
    "erişim engellendi",
    "erişiminiz engellenmiştir",
    "access denied",
    "request rejected",
)
TIMEOUT = 25.0


@dataclass
class Check:
    source: str
    label: str
    method: str
    url: str
    parse: Callable[[httpx.Response], int] | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


CHECKS = [
    Check(
        "kamuilan_sbb",
        "liste",
        "GET",
        kamuilan_sbb.BASE_URL,
        lambda r: len(kamuilan_sbb.parse(r.text)),
    ),
    Check(
        "ilan_gov",
        "liste (API)",
        "POST",
        ilan_gov.LIST_URL,
        lambda r: len(ilan_gov.parse(r.json())),
        {
            "json": {"keys": {"txv": ["8"]}, "skipCount": 0, "maxResultCount": 20},
            "headers": {**ilan_gov.API_HEADERS, "Content-Type": "application/json-patch+json"},
        },
    ),
    Check(
        "kariyer_kapisi",
        "liste (API)",
        "POST",
        kariyer_kapisi.LIST_URL,
        lambda r: len(kariyer_kapisi.parse(r.json())),
        {"json": kariyer_kapisi.LIST_BODY},
    ),
    Check(
        "iskur",
        "il listesi",
        "GET",
        iskur.LIST_URL,
        lambda r: len(iskur.parse_cities(r.text)),
    ),
    Check(
        "iskur",
        "Ankara",
        "GET",
        iskur.LIST_URL,
        lambda r: len(iskur.parse(r.text, "Ankara")),
        {"params": {"il": "Ankara"}},
    ),
    Check(
        "yerel_yonetimler",
        "liste",
        "GET",
        yerel_yonetimler.LIST_URL,
        lambda r: len(yerel_yonetimler.parse(r.text)),
    ),
    # Kapalı kaynak; yurt dışı IP'den davranışı bilgi amaçlı ölçülür (docs/kaynaklar.md).
    Check("resmi_gazete", "ana sayfa (kapalı)", "GET", "https://www.resmigazete.gov.tr/"),
]


def run_check(client: httpx.Client, check: Check) -> dict[str, str]:
    row = {"kaynak": check.source, "istek": check.label}
    started = time.monotonic()
    try:
        r = client.request(check.method, check.url, **check.kwargs)
    except Exception as e:
        row.update(durum="❌", http="-", boyut="-", sure=f"{time.monotonic() - started:.1f} sn")
        row["not"] = f"{type(e).__name__}: {str(e)[:80]}"
        return row
    elapsed = time.monotonic() - started
    body = r.text[:20000].lower() if r.content else ""
    markers = [m for m in BLOCK_MARKERS if m in body]
    notes = []
    parsed_ok = True
    if markers:
        notes.append("engel işareti: " + ", ".join(markers))
    if check.parse and r.is_success:
        try:
            notes.append(f"{check.parse(r)} kayıt parse edildi")
        except Exception as e:
            parsed_ok = False
            notes.append(f"parse hatası: {type(e).__name__}")
    ok = r.is_success and parsed_ok and not markers
    row.update(
        durum="✅" if ok else "⚠️" if r.is_success else "❌",
        http=str(r.status_code),
        boyut=f"{len(r.content) / 1024:.0f} KB",
        sure=f"{elapsed:.1f} sn",
    )
    row["not"] = "; ".join(notes)
    return row


def to_markdown(rows: list[dict[str, str]]) -> str:
    cols = ["durum", "kaynak", "istek", "http", "boyut", "sure", "not"]
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(r.get(c, "") for c in cols) + " |\n" for r in rows)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rows = []
    with make_client(timeout=TIMEOUT) as client:
        for check in CHECKS:
            rows.append(run_check(client, check))
            time.sleep(1)  # nazik istemci
    table = to_markdown(rows)
    print(table)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## Kaynak erişim testi\n\n" + table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
