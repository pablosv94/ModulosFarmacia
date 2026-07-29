from __future__ import annotations

import html
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

import requests

from .models import Change, ChangeType, ModuleAvailability, MonitorState


class NotificationError(RuntimeError):
    """Telegram rechazó la notificación."""


LABELS = {
    ChangeType.NAME_CHANGED: "Nombre",
    ChangeType.OFFERED_CHANGED: "Ofertadas",
    ChangeType.OCCUPIED_CHANGED: "Ocupadas",
    ChangeType.VACANT_CHANGED: "Vacantes",
}


def build_report_updating_message() -> str:
    return (
        "⏳ <b>El informe del CIFP Leixa todavía se está actualizando</b>\n\n"
        "Se intentó comprobar las plazas, pero el PDF aún no está disponible. "
        "Se volverá a intentar en la próxima comprobación.\n\n"
        "El último estado válido se conserva."
    )


def _module_summary(module: ModuleAvailability) -> str:
    return (
        f"{html.escape(module.code)} · {html.escape(module.name)} — "
        f"{module.offered} ofertadas, {module.occupied} ocupadas, {module.vacant} vacantes"
    )


def build_status_message(state: MonitorState, changes: Iterable[Change]) -> str:
    changes_by_module: dict[str, list[Change]] = defaultdict(list)
    removed: list[ModuleAvailability] = []
    for change in changes:
        if change.kind == ChangeType.MODULE_REMOVED:
            assert isinstance(change.old, ModuleAvailability)
            removed.append(change.old)
        elif change.module_code is not None:
            changes_by_module[change.module_code].append(change)

    has_changes = bool(changes_by_module or removed)
    lines = [
        "✅ <b>Comprobación completada en el CIFP Leixa</b>",
        "",
        f"<b>{html.escape(state.cycle.code)} · {html.escape(state.cycle.name)}</b>",
        "Se detectaron cambios:"
        if has_changes
        else "Sin cambios respecto a la comprobación anterior.",
        "",
        "<b>Asignaturas</b>",
    ]
    for module in state.modules:
        module_changes = changes_by_module.get(module.code, [])
        summary = _module_summary(module)
        added = any(change.kind == ChangeType.MODULE_ADDED for change in module_changes)
        if added:
            lines.append(f"• <b>{summary} — NUEVA</b>")
            continue
        relevant = [
            change
            for change in module_changes
            if change.kind
            in {
                ChangeType.NAME_CHANGED,
                ChangeType.OFFERED_CHANGED,
                ChangeType.OCCUPIED_CHANGED,
                ChangeType.VACANT_CHANGED,
            }
        ]
        if not relevant:
            lines.append(f"• {summary}")
            continue
        lines.append(f"• <b>{summary}</b>")
        details: list[str] = []
        for change in relevant:
            label = LABELS[change.kind]
            suffix = ""
            if change.kind == ChangeType.VACANT_CHANGED:
                delta = int(change.new) - int(change.old)  # type: ignore[arg-type]
                suffix = f" ({delta:+d})"
            details.append(
                f"{label}: {html.escape(str(change.old))} → {html.escape(str(change.new))}{suffix}"
            )
        lines.append(f"  <b>Cambios: {'; '.join(details)}</b>")
    for module in removed:
        lines.append(f"• <s>{_module_summary(module)} — ELIMINADA</s>")

    checked = datetime.fromisoformat(state.checked_at)
    lines.extend(
        [
            "",
            f"Comprobado: {checked.astimezone().strftime('%d/%m/%Y %H:%M')}",
            f'<a href="{html.escape(state.source_url, quote=True)}">Abrir informe oficial</a>',
        ]
    )
    return "\n".join(lines)


def build_change_message(state: MonitorState, changes: Iterable[Change]) -> str:
    grouped: dict[str | None, list[Change]] = defaultdict(list)
    for change in changes:
        grouped[change.module_code].append(change)
    modules = {item.code: item for item in state.modules}
    lines = [
        "🔔 <b>Cambio en las plazas del CIFP Leixa</b>",
        "",
        f"<b>{html.escape(state.cycle.code)} · {html.escape(state.cycle.name)}</b>",
    ]
    for code, items in grouped.items():
        lines.append("")
        if code is None:
            for item in items:
                lines.append(
                    f"• {html.escape(item.kind.value)}: "
                    f"{html.escape(str(item.old))} → {html.escape(str(item.new))}"
                )
            continue
        current = modules.get(code)
        removed = next((item.old for item in items if item.kind == ChangeType.MODULE_REMOVED), None)
        module = current if current is not None else removed
        assert isinstance(module, ModuleAvailability)
        lines.append(f"<b>{html.escape(code)} · {html.escape(module.name)}</b>")
        for item in items:
            if item.kind == ChangeType.MODULE_ADDED:
                lines.append(
                    f"• Módulo nuevo: {module.offered} ofertadas, "
                    f"{module.occupied} ocupadas, {module.vacant} vacantes"
                )
            elif item.kind == ChangeType.MODULE_REMOVED:
                lines.append("• Módulo eliminado del informe")
            else:
                label = LABELS[item.kind]
                suffix = ""
                if item.kind == ChangeType.VACANT_CHANGED:
                    delta = int(item.new) - int(item.old)  # type: ignore[arg-type]
                    suffix = f" ({delta:+d})"
                lines.append(
                    f"• {label}: {html.escape(str(item.old))} → "
                    f"{html.escape(str(item.new))}{suffix}"
                )
    checked = datetime.fromisoformat(state.checked_at)
    lines.extend(
        [
            "",
            f"Comprobado: {checked.astimezone().strftime('%d/%m/%Y %H:%M')}",
            f'<a href="{html.escape(state.source_url, quote=True)}">Abrir informe oficial</a>',
        ]
    )
    return "\n".join(lines)


def send_telegram(
    token: str,
    chat_id: str,
    text: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = (10, 30),
) -> None:
    if not token or not chat_id:
        raise NotificationError("faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
    client = session or requests.Session()
    try:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else exc.__class__.__name__
        raise NotificationError(f"fallo al enviar a Telegram: {detail}") from exc
    if not payload.get("ok"):
        raise NotificationError("Telegram devolvió una respuesta no válida")
