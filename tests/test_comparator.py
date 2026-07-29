from dataclasses import replace

from leixa_monitor.comparator import compare_states
from leixa_monitor.models import ChangeType, ModuleAvailability


def test_added_removed_and_values(sample_state) -> None:
    new = replace(
        sample_state,
        modules=(ModuleAvailability("MP0101", "Novo", 20, 14, 6),),
    )
    assert {change.kind for change in compare_states(sample_state, new)} == {
        ChangeType.MODULE_ADDED,
        ChangeType.MODULE_REMOVED,
    }


def test_occupied_and_vacant_changed(sample_state) -> None:
    new = replace(
        sample_state,
        modules=(ModuleAvailability("MP0100", "Oficina de farmacia", 40, 36, 4),),
    )
    changes = compare_states(sample_state, new)
    assert [change.kind for change in changes] == [
        ChangeType.OCCUPIED_CHANGED,
        ChangeType.VACANT_CHANGED,
    ]


def test_no_changes(sample_state) -> None:
    assert compare_states(sample_state, sample_state) == ()
