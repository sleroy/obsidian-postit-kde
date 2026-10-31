"""Exercise BgTask through a real Qt event loop — this is what the earlier
tests missed and let a cross-thread crash ship. Skipped if no Qt platform."""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QThread, QTimer  # noqa: E402

from obsidian_postit_kde.ui.ai_worker import BgTask  # noqa: E402


def _run_task(fn):
    app = QCoreApplication.instance() or QCoreApplication([])
    result = {}

    def done(value):
        result["value"] = value
        result["thread_is_main"] = QThread.currentThread() is app.thread()
        app.quit()

    def failed(msg):
        result["error"] = msg
        result["thread_is_main"] = QThread.currentThread() is app.thread()
        app.quit()

    task = BgTask(fn, on_done=done, on_failed=failed)
    task.start()
    QTimer.singleShot(5000, app.quit)  # safety timeout
    app.exec()
    return result


def test_bgtask_runs_and_delivers_on_main_thread():
    worker_thread = {}

    def work():
        worker_thread["id"] = threading.get_ident()
        return 21 * 2

    res = _run_task(work)
    assert res.get("value") == 42
    # Callback must fire on the main (GUI) thread — the crash was a cross-thread
    # delivery; this asserts the queued-connection fix.
    assert res.get("thread_is_main") is True
    # And the work itself ran off the main thread.
    assert worker_thread["id"] != threading.get_ident()


def test_bgtask_reports_failure_without_crashing():
    def boom():
        raise RuntimeError("kaboom")

    res = _run_task(boom)
    assert "kaboom" in res.get("error", "")
    assert res.get("thread_is_main") is True
