"""Run a blocking OpenRouter call on a worker thread, off the UI thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from ..openrouter import OpenRouterClient, OpenRouterError


class _AiWorker(QObject):
    done = Signal(str)
    failed = Signal(str)

    def __init__(
        self, fn: Callable[[OpenRouterClient, str], str], client: OpenRouterClient, text: str
    ) -> None:
        super().__init__()
        self._fn = fn
        self._client = client
        self._text = text

    def run(self) -> None:
        try:
            self.done.emit(self._fn(self._client, self._text))
        except OpenRouterError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # defensive: never let the thread die silently
            self.failed.emit(f"Unexpected error: {exc}")


class AiTask:
    """Owns a QThread + worker for a single OpenRouter request.

    Keep a reference on the caller until `on_done`/`on_failed` fires, or the
    thread may be garbage-collected mid-flight.
    """

    def __init__(
        self,
        fn: Callable[[OpenRouterClient, str], str],
        client: OpenRouterClient,
        text: str,
        on_done: Callable[[str], None],
        on_failed: Callable[[str], None],
    ) -> None:
        self._thread = QThread()
        self._worker = _AiWorker(fn, client, text)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(on_done)
        self._worker.failed.connect(on_failed)
        # Teardown: quit the loop and clean up once either signal fires.
        self._worker.done.connect(self._finish)
        self._worker.failed.connect(self._finish)

    def start(self) -> None:
        self._thread.start()

    def _finish(self, *_args: object) -> None:
        self._thread.quit()
        self._thread.wait()
        self._worker.deleteLater()
