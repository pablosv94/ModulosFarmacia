from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from .config import EXPECTED_HOST

logger = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    """Error descargando el informe."""


class ReportUpdating(DownloadError):
    """El informe está regenerándose."""


class TemporaryHTTPError(DownloadError):
    """Error HTTP recuperable."""


class UnexpectedResponse(DownloadError):
    """Respuesta que no es el PDF esperado."""


@dataclass(frozen=True, slots=True)
class DownloadedPdf:
    content: bytes
    sha256: str


def _looks_updating(html: str) -> bool:
    normalized = " ".join(html.lower().split())
    return any(
        phrase in normalized
        for phrase in (
            "informe solicitado se está actualizando",
            "informe solicitado estase actualizando",
            "informe solicitado estase a actualizar",
            "informe solicitado está a actualizar",
            "volva intentalo dentro duns minutos",
            "vuelva a intentarlo dentro de unos minutos",
        )
    )


def download_pdf(
    url: str,
    *,
    session: requests.Session | None = None,
    attempts: int = 4,
    retry_wait: float = 20,
    timeout: tuple[float, float] = (10, 45),
    max_bytes: int = 50 * 1024 * 1024,
    sleep: object = time.sleep,
) -> DownloadedPdf:
    if urlparse(url).hostname != EXPECTED_HOST:
        raise ValueError("el host del informe no es el esperado")
    client = session or requests.Session()
    client.headers.update(
        {"User-Agent": "LeixaVacancyMonitor/1.0 (+https://github.com/; uso educativo)"}
    )
    last_error: DownloadError | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url, timeout=timeout, stream=True)
        except requests.RequestException as exc:
            last_error = TemporaryHTTPError(f"error de red: {exc.__class__.__name__}")
        else:
            if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                last_error = TemporaryHTTPError(f"HTTP temporal {response.status_code}")
            elif not response.ok:
                raise DownloadError(f"HTTP {response.status_code}")
            else:
                content = response.content
                if len(content) > max_bytes:
                    raise UnexpectedResponse("el PDF supera el límite de tamaño")
                content_type = response.headers.get("Content-Type", "").lower()
                if content.startswith(b"%PDF-") and (
                    "pdf" in content_type or "octet-stream" in content_type
                ):
                    return DownloadedPdf(content, hashlib.sha256(content).hexdigest())
                if content.startswith(b"%PDF-"):
                    logger.warning(
                        "firma PDF válida con Content-Type inesperado", extra={"type": content_type}
                    )
                    return DownloadedPdf(content, hashlib.sha256(content).hexdigest())
                html = content.decode(response.encoding or "utf-8", errors="replace")
                if "html" in content_type or html.lstrip().lower().startswith(
                    ("<!doctype", "<html")
                ):
                    if _looks_updating(html):
                        last_error = ReportUpdating("el informe se está actualizando")
                    else:
                        raise UnexpectedResponse("respuesta HTML inesperada")
                else:
                    raise UnexpectedResponse("la respuesta no tiene firma PDF")
        if attempt < attempts:
            delay = (
                retry_wait
                if isinstance(last_error, ReportUpdating)
                else retry_wait * (2 ** (attempt - 1))
            )
            logger.info("reintentando descarga", extra={"attempt": attempt, "delay_seconds": delay})
            sleep(delay)  # type: ignore[operator]
    assert last_error is not None
    raise last_error
