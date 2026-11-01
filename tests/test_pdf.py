import io

import pytest
from conftest import fixture_bytes
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

from ilanbot.pdf import extract_text

READABLE = fixture_bytes("kamuilan_sbb/ilan_ebelik.pdf")
SCANNED = fixture_bytes("kamuilan_sbb/ilan_taranmis.pdf")


def test_readable_pdf():
    assert len(extract_text(READABLE)) > 1000


def test_scanned_pdf_is_unreadable():
    assert extract_text(SCANNED) is None


def test_one_scanned_page_makes_whole_pdf_unreadable():
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(READABLE)).pages[0])
    writer.add_page(PdfReader(io.BytesIO(SCANNED)).pages[0])
    out = io.BytesIO()
    writer.write(out)
    assert extract_text(out.getvalue()) is None


def test_not_a_pdf_raises():  # kamuilan, Referer'sız isteğe PDF yerine HTML hata sayfası döner
    with pytest.raises(PyPdfError):
        extract_text(b"<html>404</html>")
