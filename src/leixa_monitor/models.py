from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleAvailability:
    code: str
    name: str
    offered: int
    occupied: int
    vacant: int


@dataclass(frozen=True, slots=True)
class Entity:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class MonitorState:
    schema_version: int
    checked_at: str
    source_url: str
    pdf_sha256: str
    center: Entity
    cycle: Entity
    modules: tuple[ModuleAvailability, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MonitorState:
        if value.get("schema_version") != 1:
            raise ValueError("versión de estado no compatible")
        center = value["center"]
        cycle = value["cycle"]
        modules = tuple(ModuleAvailability(**item) for item in value["modules"])
        return cls(
            schema_version=1,
            checked_at=str(value["checked_at"]),
            source_url=str(value["source_url"]),
            pdf_sha256=str(value["pdf_sha256"]),
            center=Entity(**center),
            cycle=Entity(**cycle),
            modules=modules,
        )


class ChangeType(StrEnum):
    MODULE_ADDED = "MODULE_ADDED"
    MODULE_REMOVED = "MODULE_REMOVED"
    NAME_CHANGED = "NAME_CHANGED"
    OFFERED_CHANGED = "OFFERED_CHANGED"
    OCCUPIED_CHANGED = "OCCUPIED_CHANGED"
    VACANT_CHANGED = "VACANT_CHANGED"
    CENTER_CHANGED = "CENTER_CHANGED"
    CYCLE_CHANGED = "CYCLE_CHANGED"


@dataclass(frozen=True, slots=True)
class Change:
    kind: ChangeType
    module_code: str | None
    old: str | int | ModuleAvailability | None
    new: str | int | ModuleAvailability | None
