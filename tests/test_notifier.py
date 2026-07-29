from dataclasses import replace

import pytest
import responses

from leixa_monitor.comparator import compare_states
from leixa_monitor.models import ModuleAvailability
from leixa_monitor.notifier import NotificationError, build_change_message, send_telegram


def test_message_groups_changes_and_delta(sample_state) -> None:
    current = replace(
        sample_state,
        modules=(ModuleAvailability("MP0100", "Oficina & farmacia", 40, 36, 4),),
    )
    message = build_change_message(current, compare_states(sample_state, current))
    assert "Ocupadas: 37 → 36" in message
    assert "Vacantes: 3 → 4 (+1)" in message
    assert "Oficina &amp; farmacia" in message


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
