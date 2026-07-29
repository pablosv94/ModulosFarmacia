from dataclasses import replace

import pytest
import responses

from leixa_monitor.comparator import compare_states
from leixa_monitor.models import ModuleAvailability
from leixa_monitor.notifier import (
    NotificationError,
    build_change_message,
    build_report_updating_message,
    build_status_message,
    send_telegram,
)


def test_message_groups_changes_and_delta(sample_state) -> None:
    current = replace(
        sample_state,
        modules=(ModuleAvailability("MP0100", "Oficina & farmacia", 40, 36, 4),),
    )
    message = build_change_message(current, compare_states(sample_state, current))
    assert "Ocupadas: 37 → 36" in message
    assert "Vacantes: 3 → 4 (+1)" in message
    assert "Oficina &amp; farmacia" in message


def test_report_updating_message_explains_retry_and_preserved_state() -> None:
    message = build_report_updating_message()
    assert "todavía se está actualizando" in message
    assert "Se intentó comprobar las plazas" in message
    assert "último estado válido se conserva" in message


def test_status_message_lists_unchanged_modules(sample_state) -> None:
    message = build_status_message(sample_state, ())
    assert "Sin cambios respecto" in message
    assert (
        "<b>[MP0100 - Oficina de farmacia]</b> Ofertadas: 40, Ocupadas: 37, Vacantes: 3"
    ) in message


def test_status_message_highlights_changed_new_and_removed_modules(sample_state) -> None:
    current = replace(
        sample_state,
        modules=(
            ModuleAvailability("MP0100", "Oficina & farmacia", 40, 36, 4),
            ModuleAvailability("MP0101", "Nueva", 20, 10, 10),
        ),
    )
    previous = replace(
        sample_state,
        modules=(
            *sample_state.modules,
            ModuleAvailability("MP0999", "Antigua", 10, 10, 0),
        ),
    )
    changes = compare_states(previous, current)

    message = build_status_message(current, changes)

    assert "<b>[MP0100 - Oficina &amp; farmacia]</b>" in message
    assert "<b>Cambios:" in message
    assert "Vacantes: 3 → 4 (+1)" in message
    assert "<b>[MP0101 - Nueva]</b>" in message
    assert "<b>— NUEVA</b>" in message
    assert "<s><b>[MP0999 - Antigua]</b>" in message
    assert "ELIMINADA</s>" in message
    assert "\n\n• <b>[MP0101" in message


def test_status_message_strikes_modules_without_vacancies(sample_state) -> None:
    full = replace(
        sample_state,
        modules=(ModuleAvailability("MP0100", "Oficina", 40, 40, 0),),
    )

    message = build_status_message(full, compare_states(sample_state, full))

    assert ("<s><b>[MP0100 - Oficina]</b> Ofertadas: 40, Ocupadas: 40, Vacantes: 0</s>") in message


@responses.activate
def test_send_success() -> None:
    responses.post("https://api.telegram.org/botTOKEN/sendMessage", json={"ok": True})
    send_telegram("TOKEN", "123", "hola")
    assert responses.calls[0].request.url.endswith("/sendMessage")


@responses.activate
def test_send_http_error() -> None:
    responses.post("https://api.telegram.org/botTOKEN/sendMessage", status=401)
    with pytest.raises(NotificationError, match="HTTP 401"):
        send_telegram("TOKEN", "123", "hola")
