from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pdfplumber

from .models import Entity, ModuleAvailability

CENTER_RE = re.compile(r"^\s*(\d{8})\s*[-–·]\s*(.+?)\s*$")
CYCLE_RE = re.compile(r"^\s*([A-Z0-9]{8,12})\s*[-–·]\s*(.+?)\s*$")
MODULE_RE = re.compile(r"^\s*(MP\d{3,5}|[A-Z]{1,4}\d{3,6})\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")
NUMBERS_RE = re.compile(r"^(.*?)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")


class ExtractionError(RuntimeError):
    """No se pudo interpretar el PDF."""


class CenterNotFound(ExtractionError):
    """No aparece el centro objetivo."""


class CycleNotFound(ExtractionError):
    """No aparece el ciclo objetivo dentro del centro."""


@dataclass(frozen=True, slots=True)
class ExtractedReport:
    center: Entity
    cycle: Entity
    modules: tuple[ModuleAvailability, ...]


def extract_text(pdf: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf)) as document:
            pages = [
                page.extract_text(x_tolerance=2, y_tolerance=3) or "" for page in document.pages
            ]
    except Exception as exc:
        raise ExtractionError("PDF válido pero ilegible") from exc
    text = "\n".join(pages)
    if not text.strip():
        raise ExtractionError("el PDF no contiene texto extraíble")
    return text


def parse_report_text(
    text: str,
    center_code: str = "15021469",
    center_name: str = "CIFP Leixa",
    cycle_code: str = "ZD2SAN000",
) -> ExtractedReport:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    has_center_code = any(
        (match := CENTER_RE.match(line)) is not None and match.group(1) == center_code
        for line in lines
    )
    center: Entity | None = None
    cycle: Entity | None = None
    in_center = False
    in_cycle = False
    modules: dict[str, ModuleAvailability] = {}
    pending_code: str | None = None
    pending_name: list[str] = []

    def add(module: ModuleAvailability) -> None:
        if module.offered != module.occupied + module.vacant:
            raise ExtractionError(f"totales incompatibles en {module.code}")
        old = modules.get(module.code)
        if old is not None and old != module:
            raise ExtractionError(f"datos incompatibles repetidos para {module.code}")
        modules[module.code] = module

    for line in lines:
        if not line or _is_header(line):
            continue
        center_match = CENTER_RE.match(line)
        if center_match:
            code, name = center_match.groups()
            if code == center_code:
                center = Entity(code, name)
                in_center = True
                in_cycle = False
            elif in_center:
                break
            else:
                in_center = False
            continue
        if not has_center_code and center_name.casefold() in line.casefold():
            center = Entity(center_code, center_name)
            in_center = True
            in_cycle = False
            continue
        if not in_center:
            continue
        cycle_match = CYCLE_RE.match(line)
        if cycle_match and not line.startswith(("MP", "UF")):
            code, name = cycle_match.groups()
            if code == cycle_code:
                cycle = Entity(code, name)
                in_cycle = True
            elif in_cycle:
                break
            continue
        if not in_cycle:
            continue
        match = MODULE_RE.match(line)
        if match:
            code, name, offered, occupied, vacant = match.groups()
            add(ModuleAvailability(code, name, int(offered), int(occupied), int(vacant)))
            pending_code = None
            pending_name.clear()
            continue
        code_match = re.match(r"^\s*(MP\d{3,5}|[A-Z]{1,4}\d{3,6})\s+(.+)$", line)
        if code_match and not NUMBERS_RE.match(line):
            pending_code = code_match.group(1)
            pending_name = [code_match.group(2)]
            continue
        if pending_code:
            number_match = NUMBERS_RE.match(line)
            if number_match:
                prefix, offered, occupied, vacant = number_match.groups()
                if prefix:
                    pending_name.append(prefix)
                add(
                    ModuleAvailability(
                        pending_code,
                        " ".join(pending_name),
                        int(offered),
                        int(occupied),
                        int(vacant),
                    )
                )
                pending_code = None
                pending_name.clear()
            else:
                pending_name.append(line)
    if center is None:
        raise CenterNotFound(f"centro {center_code} no encontrado")
    if cycle is None:
        raise CycleNotFound(f"ciclo {cycle_code} no encontrado dentro de {center_code}")
    if not modules:
        raise ExtractionError("el ciclo no contiene filas de módulos reconocibles")
    return ExtractedReport(
        center, cycle, tuple(sorted(modules.values(), key=lambda item: item.code))
    )


def _is_header(line: str) -> bool:
    lowered = line.casefold()
    return (
        ("módulo" in lowered or "modulo" in lowered)
        and ("ofertad" in lowered or "ocupad" in lowered or "vacante" in lowered)
    ) or lowered.startswith(("curso:", "grao:", "grado:", "modalidade:", "modalidad:"))


def extract_report(pdf: bytes) -> ExtractedReport:
    return parse_report_text(extract_text(pdf))
