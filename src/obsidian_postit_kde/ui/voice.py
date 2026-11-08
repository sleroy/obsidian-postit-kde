"""Record a daily note and append its local transcript."""

from __future__ import annotations

from contextlib import suppress

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from ..config import Config
from ..openrouter import OpenRouterClient, OpenRouterError, has_api_key
from ..speech import Recorder, SpeechError, transcribe
from ..vault import ObsidianVault
from .ai_worker import BgTask


class VoiceNoteDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._recorder: Recorder | None = None
        self._task: BgTask | None = None
        self._processing = False
        self.setWindowTitle("Record a note")
        self.resize(380, 150)

        layout = QVBoxLayout(self)
        self.status = QLabel("Starting microphone…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.stop_btn = QPushButton("Stop and add to daily note")
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

    def _stop(self) -> None:
        assert self._recorder is not None
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

        model = self.config.speech_model
        language = self.config.speech_language
        clean = self.config.speech_clean_with_openrouter
        router_model = self.config.openrouter_model

        def work() -> tuple[str, str | None]:
            text = transcribe(audio, model, language)
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
        text, warning = result
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
        self._processing = False
        self._task = None
        QMessageBox.warning(self, "Transcription failed", error)
        self.reject()

    def reject(self) -> None:
        if self._processing:
            return
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
