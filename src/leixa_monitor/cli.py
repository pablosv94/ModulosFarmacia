from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .comparator import compare_states
from .config import SOURCE_URL, Settings
from .downloader import DownloadError, ReportUpdating, download_pdf
from .extractor import CenterNotFound, CycleNotFound, ExtractionError, extract_report
from .models import Change, ChangeType, MonitorState
from .notifier import NotificationError, build_change_message, send_telegram
from .state import (
    HealthState,
    StateError,
    load_health,
    load_state,
    save_health,
    save_state,
)

logger = logging.getLogger("leixa_monitor")
EXIT_OK = 0
EXIT_TEMPORARY = 2
EXIT_ERROR = 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vigila las plazas de Farmacia del CIFP Leixa")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--retry-wait", type=float, default=20)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="descarga, compara y actualiza el estado")
    check.add_argument("--dry-run", action="store_true", help="no envía Telegram ni guarda estado")
    check.add_argument("--force-notify", action="store_true")
    sub.add_parser("send-test-notification", help="prueba Telegram sin tocar el estado")
    sub.add_parser("print-current", help="muestra el último estado guardado")
    return parser


def _print_table(state: MonitorState) -> None:
    headers = ("Código", "Módulo", "Ofertadas", "Ocupadas", "Vacantes")
    rows = [(m.code, m.name, str(m.offered), str(m.occupied), str(m.vacant)) for m in state.modules]
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]
    print("  ".join(value.ljust(widths[i]) for i, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


def _notify(settings: Settings, text: str, dry_run: bool) -> None:
    if dry_run:
        logger.info("notificación omitida por --dry-run")
        return
    send_telegram(settings.bot_token or "", settings.chat_id or "", text)


def _error_category(exc: BaseException) -> str:
    if isinstance(exc, ReportUpdating):
        return "Informe todavía actualizándose"
    if isinstance(exc, CenterNotFound):
        return "Centro no encontrado"
    if isinstance(exc, CycleNotFound):
        return "Ciclo no encontrado"
    if isinstance(exc, ExtractionError):
        return "Fallo de extracción"
    if isinstance(exc, DownloadError):
        return "Error de red o formato inesperado"
    return "Error interno"


def _record_failure(settings: Settings, exc: BaseException, dry_run: bool) -> None:
    health_path = settings.data_dir / "health.json"
    try:
        previous = load_health(health_path)
    except StateError:
        previous = HealthState()
    category = _error_category(exc)
    current = HealthState(previous.consecutive_failures + 1, previous.alerted, category)
    if current.consecutive_failures >= 3 and not current.alerted:
        text = (
            "⚠️ <b>Problema persistente en el monitor del CIFP Leixa</b>\n\n"
            f"{category}\n"
            f"Fallos consecutivos: {current.consecutive_failures}\n\n"
            "El último estado válido se conserva."
        )
        try:
            _notify(settings, text, dry_run)
        except NotificationError:
            logger.exception("no se pudo enviar la alerta de error")
        else:
            current = HealthState(current.consecutive_failures, not dry_run, category)
    if not dry_run:
        save_health(health_path, current)


def _record_success(settings: Settings, dry_run: bool) -> None:
    health_path = settings.data_dir / "health.json"
    try:
        previous = load_health(health_path)
    except StateError:
        previous = HealthState()
    if previous.alerted:
        text = (
            "✅ <b>Monitor del CIFP Leixa recuperado</b>\n\n"
            f"Vuelve a funcionar tras {previous.consecutive_failures} fallos consecutivos."
        )
        _notify(settings, text, dry_run)
    if not dry_run:
        save_health(health_path, HealthState())


def _check(settings: Settings, *, dry_run: bool, force_notify: bool) -> int:
    state_path = settings.data_dir / "state.json"
    try:
        old = load_state(state_path)
        downloaded = download_pdf(
            SOURCE_URL,
            attempts=settings.attempts,
            retry_wait=settings.retry_wait,
            timeout=(settings.connect_timeout, settings.read_timeout),
            max_bytes=settings.max_pdf_bytes,
        )
        if old is not None and old.pdf_sha256 == downloaded.sha256:
            logger.info("PDF sin cambios; se omite la extracción")
            _record_success(settings, dry_run)
            _print_table(old)
            return EXIT_OK
        report = extract_report(downloaded.content)
        current = MonitorState(
            schema_version=1,
            checked_at=datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds"),
            source_url=SOURCE_URL,
            pdf_sha256=downloaded.sha256,
            center=report.center,
            cycle=report.cycle,
            modules=report.modules,
        )
        changes: tuple[Change, ...]
        if old is None:
            initial_changes = (
                Change(ChangeType.MODULE_ADDED, module.code, None, module)
                for module in current.modules
            )
            changes = tuple(initial_changes) if settings.notify_on_first_run else ()
        else:
            changes = compare_states(old, current)
        _print_table(current)
        if changes or force_notify:
            if force_notify and not changes:
                forced_changes = (
                    Change(ChangeType.MODULE_ADDED, module.code, None, module)
                    for module in current.modules
                )
                changes = tuple(forced_changes)
            _notify(settings, build_change_message(current, changes), dry_run)
        if not dry_run:
            save_state(state_path, current)
        _record_success(settings, dry_run)
        logger.info("comprobación completada", extra={"changes": len(changes)})
        return EXIT_OK
    except (StateError, DownloadError, ExtractionError, NotificationError) as exc:
        logger.error("%s: %s", _error_category(exc), exc)
        if not isinstance(exc, StateError):
            _record_failure(settings, exc, dry_run)
        return EXIT_TEMPORARY if isinstance(exc, ReportUpdating) else EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.attempts < 1 or args.retry_wait < 0:
        logger.error("--attempts debe ser >= 1 y --retry-wait >= 0")
        return EXIT_ERROR
    settings = Settings.from_env(args.data_dir, args.attempts, args.retry_wait)
    if args.command == "check":
        return _check(settings, dry_run=args.dry_run, force_notify=args.force_notify)
    if args.command == "send-test-notification":
        try:
            _notify(
                settings,
                "✅ <b>Prueba del monitor CIFP Leixa</b>\n\n"
                "Telegram está configurado correctamente.",
                False,
            )
        except NotificationError as exc:
            logger.error("%s", exc)
            return EXIT_ERROR
        return EXIT_OK
    try:
        state = load_state(settings.data_dir / "state.json")
    except StateError as exc:
        logger.error("%s", exc)
        return EXIT_ERROR
    if state is None:
        logger.error("todavía no existe un estado válido")
        return EXIT_ERROR
    _print_table(state)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
