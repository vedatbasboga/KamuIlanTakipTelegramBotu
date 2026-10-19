"""CLI giriş noktası: `python -m ilanbot`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from . import runner
from .config import ConfigError, load_config
from .http import make_client
from .models import Ilan, now
from .notifier import NotifierConfigError, format_ilan, notifier_from_env
from .sources import REGISTRY, SOURCE_NAMES
from .state import StateError, load_state, prune, save_state

log = logging.getLogger("ilanbot")


def load_dotenv(path: str | Path = ".env") -> None:
    """Basit .env okuyucu: `KEY=VALUE` satırları. Ortamda zaten olan değişkeni ezmez."""
    path = Path(path)
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def test_telegram() -> int:
    """Bağlantı testi mesajı ve örnek (sahte) bir ilan kartı gönderir."""
    with make_client() as client:
        try:
            notifier = notifier_from_env(client)
        except NotifierConfigError as e:
            log.error("HATA: %s", e)
            return 2
        t = now()
        sample = Ilan(
            source="kamuilan_sbb",
            id="ornek",
            title="Örnek İlan — Sözleşmeli Bilişim Personeli Alımı (bu bir testtir)",
            url="https://kamuilan.sbb.gov.tr/",
            institution="T.C. Örnek Bakanlığı & Bağlı Kuruluşları",
            deadline=t + timedelta(days=9),
            education_levels=frozenset({"lisans"}),
            kpss_types=frozenset({"P3"}),
            locations=frozenset({"İZMİR"}),
            position_count=12,
        )
        ok = notifier.send("✅ Kamu İlan Botu bağlantı testi")
        ok = notifier.send(format_ilan(sample, t)) and ok
    if ok:
        log.info("Test mesajları gönderildi. Telefonunu kontrol et.")
        return 0
    log.error("Test mesajları gönderilemedi (ayrıntı yukarıda).")
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ilanbot",
        description="KPSS kamu ilanlarını takip eder, yeni ilanları Telegram'a gönderir.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Telegram'a göndermez, mesajları konsola yazar, state kaydetmez.",
    )
    p.add_argument(
        "--source",
        action="append",
        metavar="NAME",
        choices=SOURCE_NAMES,
        help="Sadece bu kaynağı çalıştır (tekrarlanabilir).",
    )
    p.add_argument(
        "--config", default="config.yaml", help="Config dosyası (varsayılan: %(default)s)"
    )
    p.add_argument(
        "--state", default="data/state.json", help="State dosyası (varsayılan: %(default)s)"
    )
    p.add_argument("--no-save", action="store_true", help="Gönderir ama state kaydetmez (debug).")
    p.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı (debug) log.")
    p.add_argument(
        "--test-telegram",
        action="store_true",
        help="Telegram'a bağlantı testi ve örnek ilan kartı gönderir, başka bir şey yapmaz.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows konsolunda Türkçe karakter/emoji için
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )
    # httpx her isteği INFO'da loglar; URL'de token geçebileceği için susturulur.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    load_dotenv()

    if args.test_telegram:
        return test_telegram()

    try:
        config = load_config(args.config)
        state = load_state(args.state)
    except (ConfigError, StateError) as e:
        log.error("HATA: %s", e)
        return 2

    names = args.source or config.enabled_sources
    if args.source:
        disabled = [n for n in args.source if not config.sources.get(n)]
        if disabled:
            log.info("Not: %s config'te kapalı ama --source ile istendi.", ", ".join(disabled))
    sources = []
    for name in names:
        if name in REGISTRY:
            sources.append(REGISTRY[name])
        else:
            log.warning("[%s] henüz uygulanmadı, atlanıyor.", name)

    if args.dry_run:
        log.info("Dry-run: bildirim gönderilmeyecek, state kaydedilmeyecek.")

    with make_client() as client:
        summary = runner.run(sources, config, state, client)

    if args.dry_run or args.no_save:
        log.info("State kaydedilmedi.")
    else:
        removed = prune(state, config.state.prune_after_days)
        if removed:
            log.info("%d eski kayıt state'ten silindi.", removed)
        save_state(args.state, state)

    return 1 if summary.all_failed else 0


if __name__ == "__main__":
    sys.exit(main())
