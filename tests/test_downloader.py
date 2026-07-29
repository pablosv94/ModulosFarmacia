from pathlib import Path

import pytest
import responses

from leixa_monitor.config import SOURCE_URL
from leixa_monitor.downloader import ReportUpdating, UnexpectedResponse, download_pdf

FIXTURES = Path(__file__).parent / "fixtures"


@responses.activate
def test_pdf_response() -> None:
    responses.get(SOURCE_URL, body=b"%PDF-1.7 fixture", content_type="application/pdf")
    result = download_pdf(SOURCE_URL, attempts=1)
    assert result.content.startswith(b"%PDF-")
    assert len(result.sha256) == 64


@responses.activate
def test_updating_retries() -> None:
    body = (FIXTURES / "updating.html").read_bytes()
    responses.get(SOURCE_URL, body=body, content_type="text/html")
    responses.get(SOURCE_URL, body=body, content_type="text/html")
    delays = []
    with pytest.raises(ReportUpdating):
        download_pdf(SOURCE_URL, attempts=2, retry_wait=0, sleep=delays.append)
    assert len(responses.calls) == 2


@responses.activate
def test_unexpected_html() -> None:
    responses.get(
        SOURCE_URL,
        body=(FIXTURES / "unexpected.html").read_bytes(),
        content_type="text/html",
    )
    with pytest.raises(UnexpectedResponse):
        download_pdf(SOURCE_URL, attempts=1)


def test_rejects_arbitrary_host() -> None:
    with pytest.raises(ValueError, match="host"):
        download_pdf("https://example.org/file.pdf", attempts=1)
