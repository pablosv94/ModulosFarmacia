from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .models import MonitorState


class StateError(RuntimeError):
    """Estado persistente inválido."""


@dataclass(frozen=True, slots=True)
class HealthState:
    consecutive_failures: int = 0
    alerted: bool = False
    last_category: str | None = None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"estado corrupto: {path.name}") from exc
    if not isinstance(value, dict):
        raise StateError(f"estado corrupto: {path.name}")
    return value


def load_state(path: Path) -> MonitorState | None:
    if not path.exists():
        return None
    try:
        return MonitorState.from_dict(_read_json(path))
    except (KeyError, TypeError, ValueError) as exc:
        raise StateError(f"estado corrupto: {path.name}") from exc


def save_state(path: Path, state: MonitorState) -> None:
    _atomic_json(path, state.to_dict())


def load_health(path: Path) -> HealthState:
    if not path.exists():
        return HealthState()
    try:
        return HealthState(**_read_json(path))
    except (KeyError, TypeError, ValueError) as exc:
        raise StateError(f"estado de salud corrupto: {path.name}") from exc


def save_health(path: Path, health: HealthState) -> None:
    _atomic_json(path, asdict(health))


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(name)
        raise
