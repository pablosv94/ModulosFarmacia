import pytest

from leixa_monitor.config import SOURCE_URL
from leixa_monitor.downloader import ReportUpdating, download_pdf


@pytest.mark.integration
def test_real_endpoint() -> None:
    try:
        result = download_pdf(SOURCE_URL, attempts=1)
    except ReportUpdating:
        pytest.skip("la Xunta está regenerando el informe")
    assert result.content.startswith(b"%PDF-")
