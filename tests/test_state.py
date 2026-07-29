import json

import pytest

from leixa_monitor.state import StateError, load_state, save_state


def test_roundtrip_atomic(tmp_path, sample_state) -> None:
    path = tmp_path / "state.json"
    save_state(path, sample_state)
    assert load_state(path) == sample_state
    assert not list(tmp_path.glob("*.tmp"))


def test_corrupt_state(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(StateError, match="corrupto"):
        load_state(path)


def test_first_run_is_absent(tmp_path) -> None:
    assert load_state(tmp_path / "state.json") is None


def test_json_has_required_fields(tmp_path, sample_state) -> None:
    path = tmp_path / "state.json"
    save_state(path, sample_state)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert {"schema_version", "checked_at", "source_url", "pdf_sha256", "modules"} <= payload.keys()
