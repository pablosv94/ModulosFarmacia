from __future__ import annotations

from .models import Change, ChangeType, MonitorState


def compare_states(old: MonitorState, new: MonitorState) -> tuple[Change, ...]:
    changes: list[Change] = []
    if old.center != new.center:
        changes.append(Change(ChangeType.CENTER_CHANGED, None, old.center.name, new.center.name))
    if old.cycle != new.cycle:
        changes.append(Change(ChangeType.CYCLE_CHANGED, None, old.cycle.name, new.cycle.name))
    before = {item.code: item for item in old.modules}
    after = {item.code: item for item in new.modules}
    for code in sorted(before.keys() - after.keys()):
        changes.append(Change(ChangeType.MODULE_REMOVED, code, before[code], None))
    for code in sorted(after.keys() - before.keys()):
        changes.append(Change(ChangeType.MODULE_ADDED, code, None, after[code]))
    fields = (
        ("name", ChangeType.NAME_CHANGED),
        ("offered", ChangeType.OFFERED_CHANGED),
        ("occupied", ChangeType.OCCUPIED_CHANGED),
        ("vacant", ChangeType.VACANT_CHANGED),
    )
    for code in sorted(before.keys() & after.keys()):
        for field, kind in fields:
            old_value = getattr(before[code], field)
            new_value = getattr(after[code], field)
            if old_value != new_value:
                changes.append(Change(kind, code, old_value, new_value))
    return tuple(changes)
