"""Record a daily note and append its local transcript."""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import openrouter
from ..config import Config
from ..openrouter import OpenRouterClient, OpenRouterError, has_api_key
from ..speech import SAMPLE_RATE, LiveTranscript, Recorder, SpeechError, SpeechWorker
from ..vault import ObsidianVault
from .ai_worker import BgTask

PREVIEW_INTERVAL_MS = 2000


class VoiceNoteDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._recorder: Recorder | None = None
        self._task: BgTask | None = None
        self._preview_task: BgTask | None = None
        self._processing = False
        self._closed = False
        self._live_ticks = 0
        self._worker: SpeechWorker | None = None
        self._worker_lock = threading.Lock()
        self._live = LiveTranscript(self._transcribe_chunk)
        self.setWindowTitle("Record a note")
        self.resize(460, 280)

        layout = QVBoxLayout(self)
        self.status = QLabel("Starting microphone…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("The transcript appears here as you speak…")
        self.preview.setAccessibleName("Live transcript")
        layout.addWidget(self.preview, 1)
        if not config.speech_live_preview:
            self.preview.hide()
            self.resize(420, 130)
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(PREVIEW_INTERVAL_MS)
        self._preview_timer.timeout.connect(self._tick)
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.stop_btn = QPushButton("Stop and add to daily note")
        self.stop_btn.setObjectName("Primary")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.stop_btn)
        layout.addLayout(buttons)
        QTimer.singleShot(0, self._start)

    def _start(self) -> None:
        if not self.isVisible():
            return
        try:
            self._recorder = Recorder()
        except SpeechError as exc:
            QMessageBox.warning(self, "Recording unavailable", str(exc))
            self.reject()
            return
        self.status.setText("Recording… Speak now, then stop to append the note.")
        self.stop_btn.setEnabled(True)
        if self.config.speech_live_preview:
            self._preview_timer.start()

    # ---- speech engine (worker threads only) ------------------------------

    def _transcribe_chunk(self, audio) -> str:
        c = self.config
        if c.speech_engine == "openrouter":
            if self._closed:
                raise SpeechError("Recording was cancelled.")
            try:
                return openrouter.transcribe(
                    audio, SAMPLE_RATE, c.speech_cloud_model, c.speech_language
                )
            except OpenRouterError as exc:
                raise SpeechError(str(exc)) from exc
        with self._worker_lock:
            if self._closed:
                raise SpeechError("Recording was cancelled.")
            if self._worker is None:
                self._worker = SpeechWorker(self.config.speech_model, self.config.speech_language)
            worker = self._worker
        return worker.transcribe(audio)

    def _close_worker(self) -> None:
        with self._worker_lock:
            worker, self._worker = self._worker, None
        if worker is not None:
            # close() may wait for the child; never block the UI thread on it.
            threading.Thread(target=worker.close, name="speech-close", daemon=True).start()

    # ---- live preview ------------------------------------------------------

    def _tick(self) -> None:
        if self._recorder is None or self._preview_task is not None:
            return
        audio = self._recorder.snapshot()
        if len(audio) < SAMPLE_RATE:  # wait for at least a second of audio
            return
        if self._live_ticks == 0:
            self.status.setText("Recording… (starting the live transcript)")
        self._live_ticks += 1
        self._preview_task = BgTask(
            lambda: self._live.update(audio), self._preview_done, self._preview_failed
        )
        self._preview_task.start()

    def _preview_done(self, text: object) -> None:
        self._preview_task = None
        if self._closed or self._recorder is None:
            return
        self.status.setText("Recording… Speak now, then stop to append the note.")
        self.preview.setPlainText(str(text))
        bar = self.preview.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _preview_failed(self, error: str) -> None:
        self._preview_task = None
        if self._closed or self._recorder is None:
            return
        self._preview_timer.stop()  # don't hammer a broken engine
        self._close_worker()  # the final pass will start a fresh one
        self.status.setText(f"Live transcript unavailable; recording continues.\n{error}")

    # ---- stop / save -------------------------------------------------------

    def _stop(self) -> None:
        assert self._recorder is not None
        self._preview_timer.stop()
        try:
            audio = self._recorder.stop()
        except Exception as exc:
            QMessageBox.warning(self, "Recording failed", str(exc))
            self.reject()
            return
        self._recorder = None
        self._processing = True
        self.stop_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.status.setText("Transcribing on this machine…")

        clean = self.config.speech_clean_with_openrouter
        router_model = self.config.openrouter_model

        live = self._live

        def work() -> tuple[str, str | None]:
            try:
                text = live.update(audio)  # waits for any in-flight preview
            except SpeechError:
                # The persistent engine died: one fresh attempt on the whole clip.
                self._close_worker()
                text = self._transcribe_chunk(audio)
            if not text:
                raise SpeechError("No speech was detected. Nothing was added to the daily note.")
            if clean:
                if not has_api_key():
                    return text, "OpenRouter cleanup skipped: no API key is configured."
                try:
                    cleaned = OpenRouterClient(router_model).clean(text)
                    if cleaned:
                        text = cleaned
                except OpenRouterError as exc:
                    return text, f"OpenRouter cleanup failed; the raw transcript was saved: {exc}"
            return text, None

        self._task = BgTask(work, self._done, self._failed)
        self._task.start()

    def _done(self, result: object) -> None:
        self._close_worker()
        text, warning = cast("tuple[str, str | None]", result)
        try:
            path = ObsidianVault(self.config).append_diary_entry(text)
        except Exception as exc:
            self._failed(f"Could not append the daily note: {exc}\n\nTranscript:\n{text}")
            return
        self._processing = False
        self._task = None
        if warning:
            QMessageBox.warning(self, "Note saved", f"Added to {path.name}.\n\n{warning}")
        else:
            QMessageBox.information(self, "Note saved", f"Added to {path.name}.")
        self.accept()

    def _failed(self, error: str) -> None:
        self._close_worker()
        self._processing = False
        self._task = None
        QMessageBox.warning(self, "Transcription failed", error)
        self.reject()

    def reject(self) -> None:
        if self._processing:
            return
        self._closed = True
        self._preview_timer.stop()
        self._close_worker()
        if self._recorder is not None:
            with suppress(Exception):
                self._recorder.discard()
            self._recorder = None
        super().reject()

    def closeEvent(self, event) -> None:
        if self._processing:
            event.ignore()
        else:
            super().closeEvent(event)
