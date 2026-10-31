"""Shared test fixtures.

Qt aborts at interpreter shutdown if multiple QApplication instances (or a
mix of QApplication and QCoreApplication) are created across tests. Provide a
single, session-wide QApplication so GUI tests share one instance.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _qt_app():
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        yield None
        return
    app = QApplication.instance() or QApplication([])
    yield app
    # Do not call app.quit()/exit here — let the interpreter drop it cleanly.
