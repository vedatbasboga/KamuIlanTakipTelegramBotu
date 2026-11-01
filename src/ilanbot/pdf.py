"""İlan PDF'lerinden metin çıkarma."""

from __future__ import annotations

import io
import logging

from pypdf import PageObject, PdfReader

from .text import squash_spaces

logging.getLogger("pypdf").setLevel(logging.ERROR)  # bozuk font uyarıları logu boğuyor

MIN_PAGE_CHARS = 50  # bundan az metinli, görüntü içeren sayfa taranmış sayılır


def extract_text(data: bytes) -> str | None:
    """PDF'in düz metni. Taranmış sayfa varsa None: ilanın bir kısmı okunamamış demektir.

    Resmî Gazete kupürlerinde yalnızca başlık metin, kadro tablosu görüntü olabiliyor; kısmi metni
    döndürmek "bu ilanda aranan meslek yok" gibi yanlış bir sonuca götürür.
    """
    pages = PdfReader(io.BytesIO(data)).pages
    texts = [squash_spaces(page.extract_text() or "") for page in pages]
    if not any(texts) or any(_is_scanned(p, t) for p, t in zip(pages, texts, strict=True)):
        return None
    return " ".join(texts)


def _is_scanned(page: PageObject, text: str) -> bool:
    return len(text) < MIN_PAGE_CHARS and len(page.images) > 0
