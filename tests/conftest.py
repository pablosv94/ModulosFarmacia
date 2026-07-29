from __future__ import annotations

from datetime import datetime

import pytest

from leixa_monitor.models import Entity, ModuleAvailability, MonitorState


@pytest.fixture
def sample_state() -> MonitorState:
    return MonitorState(
        1,
        datetime(2026, 7, 29, 16, 10).astimezone().isoformat(),
        "https://www.edu.xunta.gal/example.pdf",
        "abc",
        Entity("15021469", "CIFP Leixa"),
        Entity("ZD2SAN000", "Farmacia e parafarmacia"),
        (ModuleAvailability("MP0100", "Oficina de farmacia", 40, 37, 3),),
    )
