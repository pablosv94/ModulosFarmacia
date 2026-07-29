from pathlib import Path

import pytest

from leixa_monitor.extractor import CenterNotFound, ExtractionError, parse_report_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_hierarchical_parser_multiline_headers_and_duplicates() -> None:
    report = parse_report_text((FIXTURES / "report.txt").read_text(encoding="utf-8"))
    assert report.center.name == "CIFP Leixa"
    assert report.cycle.code == "ZD2SAN000"
    assert [item.code for item in report.modules] == ["MP0100", "MP0101", "MP0102"]
    assert report.modules[1].name == "Dispensación de produtos farmacéuticos"


def test_center_missing() -> None:
    with pytest.raises(CenterNotFound):
        parse_report_text("15000001 - Outro centro")


def test_inconsistent_total() -> None:
    text = "15021469 - CIFP Leixa\nZD2SAN000 - Farmacia e parafarmacia\nMP0100 Nome 10 8 3"
    with pytest.raises(ExtractionError, match="totales"):
        parse_report_text(text)


def test_conflicting_duplicate() -> None:
    text = (
        "15021469 - CIFP Leixa\nZD2SAN000 - Farmacia e parafarmacia\n"
        "MP0100 Nome 10 8 2\nMP0100 Nome 10 7 3"
    )
    with pytest.raises(ExtractionError, match="incompatibles"):
        parse_report_text(text)
