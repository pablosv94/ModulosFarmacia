from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SOURCE_URL = (
    "https://www.edu.xunta.gal/ciclosadmision/publico/HistorialAlumno.do"
    "?DIALOG-EVENT-listaxeModulosLiberados=listaxeModulosLiberados"
    "&ano=2026&grao=M&tipo=D"
)
EXPECTED_HOST = "www.edu.xunta.gal"


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    attempts: int = 5
    retry_wait: float = 3.0
    connect_timeout: float = 10.0
    read_timeout: float = 45.0
    max_pdf_bytes: int = 50 * 1024 * 1024
    notify_on_first_run: bool = False
    bot_token: str | None = None
    chat_id: str | None = None

    @classmethod
    def from_env(cls, data_dir: Path, attempts: int, retry_wait: float) -> Settings:
        return cls(
            data_dir=data_dir,
            attempts=attempts,
            retry_wait=retry_wait,
            notify_on_first_run=os.getenv("NOTIFY_ON_FIRST_RUN", "").lower()
            in {"1", "true", "yes", "sí", "si"},
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        )
