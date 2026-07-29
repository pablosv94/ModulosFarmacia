from __future__ import annotations

from leixa_monitor import cli
from leixa_monitor.config import Settings
from leixa_monitor.downloader import DownloadedPdf, ReportUpdating
from leixa_monitor.state import load_state, save_state


def test_updating_report_notifies_immediately_and_preserves_state(
    tmp_path, sample_state, monkeypatch
) -> None:
    state_path = tmp_path / "state.json"
    save_state(state_path, sample_state)
    messages: list[str] = []

    def fail_download(*args, **kwargs) -> None:
        raise ReportUpdating("el informe se está actualizando")

    monkeypatch.setattr(cli, "download_pdf", fail_download)
    monkeypatch.setattr(
        cli,
        "send_telegram",
        lambda token, chat_id, text: messages.append(text),
    )
    settings = Settings(
        data_dir=tmp_path,
        attempts=1,
        bot_token="test-token",
        chat_id="test-chat",
    )

    result = cli._check(settings, dry_run=False, force_notify=False)

    assert result == cli.EXIT_TEMPORARY
    assert len(messages) == 1
    assert "todavía se está actualizando" in messages[0]
    assert load_state(state_path) == sample_state


def test_updating_report_does_not_duplicate_persistent_alert(
    tmp_path, sample_state, monkeypatch
) -> None:
    save_state(tmp_path / "state.json", sample_state)
    messages: list[str] = []

    def fail_download(*args, **kwargs) -> None:
        raise ReportUpdating("actualizando")

    monkeypatch.setattr(cli, "download_pdf", fail_download)
    monkeypatch.setattr(
        cli,
        "send_telegram",
        lambda token, chat_id, text: messages.append(text),
    )
    settings = Settings(data_dir=tmp_path, bot_token="test-token", chat_id="test-chat")

    for _ in range(3):
        assert cli._check(settings, dry_run=False, force_notify=False) == cli.EXIT_TEMPORARY

    assert len(messages) == 3
    assert all("todavía se está actualizando" in message for message in messages)


def test_unchanged_pdf_sends_current_modules(tmp_path, sample_state, monkeypatch) -> None:
    save_state(tmp_path / "state.json", sample_state)
    messages: list[str] = []

    monkeypatch.setattr(
        cli,
        "download_pdf",
        lambda *args, **kwargs: DownloadedPdf(b"%PDF-same", sample_state.pdf_sha256),
    )
    monkeypatch.setattr(
        cli,
        "send_telegram",
        lambda token, chat_id, text: messages.append(text),
    )
    settings = Settings(data_dir=tmp_path, bot_token="test-token", chat_id="test-chat")

    assert cli._check(settings, dry_run=False, force_notify=False) == cli.EXIT_OK

    assert len(messages) == 1
    assert "Sin cambios respecto" in messages[0]
    assert "<b>[MP0100 - Oficina de farmacia]</b>" in messages[0]
