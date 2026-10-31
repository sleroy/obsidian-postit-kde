"""Run a blocking OpenRouter call on a worker thread, off the UI thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal

from ..openrouter import OpenRouterClient, OpenRouterError


class _BgSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _BgRunnable(QRunnable):
    def __init__(self, fn: Callable[[], object], signals: _BgSignals) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # never let the worker thread crash
            self._signals.failed.emit(str(exc))
            return
        self._signals.done.emit(result)


class BgTask:
    """Run any zero-argument callable on the global thread pool and deliver the
    result back on the **main** thread.

    `fn` runs on a worker thread, so it must not touch Qt widgets. The on_done/
    on_failed callbacks are invoked via queued signals, i.e. on the GUI thread,
    so they may safely update the UI. Keep a reference to the BgTask on the
    caller until a callback fires.
    """

    def __init__(
        self,
        fn: Callable[[], object],
        on_done: Callable[[object], None],
        on_failed: Callable[[str], None],
    ) -> None:
        self._signals = _BgSignals()
        # Queued connections guarantee the slots run on the thread that owns
        # _signals (the main thread), not on the pool worker.
        self._signals.done.connect(on_done, Qt.ConnectionType.QueuedConnection)
        self._signals.failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
        self._runnable = _BgRunnable(fn, self._signals)

    def start(self) -> None:
        QThreadPool.globalInstance().start(self._runnable)


class AiTask:
    """Run a single OpenRouter request off the UI thread, delivering the result
    on the main thread. Thin wrapper over BgTask (same safe QThreadPool path).

    Keep a reference on the caller until on_done/on_failed fires.
    """

    def __init__(
        self,
        fn: Callable[[OpenRouterClient, str], str],
        client: OpenRouterClient,
        text: str,
        on_done: Callable[[str], None],
        on_failed: Callable[[str], None],
    ) -> None:
        def work() -> object:
            try:
                return fn(client, text)
            except OpenRouterError:
                raise
            except Exception as exc:  # normalise unexpected errors
                raise OpenRouterError(f"Unexpected error: {exc}") from exc

        self._task = BgTask(
            work,
            on_done=lambda result: on_done(str(result)),
            on_failed=on_failed,
        )

    def start(self) -> None:
        self._task.start()
