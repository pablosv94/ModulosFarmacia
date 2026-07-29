from __future__ import annotations

from dataclasses import replace

from .models import MonitorState

EXCLUDED_MODULE_CODES = frozenset({"MP1708", "MO0003", "MP1664", "MP1710"})


def is_excluded_module(code: str) -> bool:
    return code in EXCLUDED_MODULE_CODES


def filter_excluded_modules(state: MonitorState) -> MonitorState:
    modules = tuple(module for module in state.modules if not is_excluded_module(module.code))
    if modules == state.modules:
        return state
    return replace(state, modules=modules)
