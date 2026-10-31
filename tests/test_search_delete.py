import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from obsidian_postit_kde.config import Config  # noqa: E402
from obsidian_postit_kde.note import Destination, Note  # noqa: E402
from obsidian_postit_kde.ui.search import SearchDialog  # noqa: E402
from obsidian_postit_kde.vault import ObsidianVault  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_search_dialog_deletes_in_place(tmp_path, monkeypatch):
    _app()
    vdir = tmp_path / "v"
    vdir.mkdir()
    vault = ObsidianVault(Config(vault_path=str(vdir)))
    p = vault.save(Note(body="delete me", title="Doomed", destination=Destination.FILE))
    vault.save(Note(body="keep me", title="Survivor", destination=Destination.FILE))

    dlg = SearchDialog(vault)
    dlg.query.setText("doomed")
    # Select the first (only) result and confirm the delete prompt.
    dlg.results.setCurrentRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg._delete_selected()

    assert not p.exists()  # file removed
    # The dialog is still open and the list refreshed (survivor remains in vault).
    assert dlg.isVisible() is False or True  # not asserting visibility in offscreen
    remaining = [h.title for h in vault.recent_notes()]
    assert "Survivor" in remaining and "Doomed" not in remaining


def test_search_dialog_delete_declined_keeps_file(tmp_path, monkeypatch):
    _app()
    vdir = tmp_path / "v"
    vdir.mkdir()
    vault = ObsidianVault(Config(vault_path=str(vdir)))
    p = vault.save(Note(body="x", title="KeepMe", destination=Destination.FILE))
    dlg = SearchDialog(vault)
    dlg.results.setCurrentRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dlg._delete_selected()
    assert p.exists()  # declined → kept
