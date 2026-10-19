"""CLI giriş noktası: `python -m ilanbot`."""

from __future__ import annotations

import argparse
import logging
import sys

from . import runner
from .config import ConfigError, load_config
from .http import make_client
from .sources import REGISTRY, SOURCE_NAMES
from .state import StateError, load_state, prune, save_state

log = logging.getLogger("ilanbot")


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
