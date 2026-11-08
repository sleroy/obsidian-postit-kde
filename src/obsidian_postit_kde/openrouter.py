"""OpenRouter integration: summarize / clean text. Key stored in keyring.

The API key is never written to the TOML config. It is kept in the system
secret service (KDE Wallet / libsecret) via `keyring`, with the
`OPENROUTER_API_KEY` environment variable as a fallback.
"""

from __future__ import annotations

import os

import httpx

from .config import APP_ID

_KEYRING_SERVICE = APP_ID
_KEYRING_USER = "openrouter_api_key"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_STT_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_HEADERS = {
    "HTTP-Referer": "https://github.com/sleroy/obsidian-postit-kde",
    "X-Title": "obsidian-postit-kde",
}

# Speech-to-text models offered in Settings: (id, label). Prices are per hour of
# audio from OpenRouter's Models API (Nov 2026); see openrouter.ai/models.
STT_MODELS: tuple[tuple[str, str], ...] = (
    ("openai/whisper-large-v3-turbo", "Whisper Large v3 Turbo — ~$0.01/h, fast (recommended)"),
    ("qwen/qwen3-asr-0.6b", "Qwen3 ASR 0.6B — ~$0.01/h"),
    ("openai/whisper-large-v3", "Whisper Large v3 — ~$0.03/h, slightly more accurate"),
    ("mistralai/voxtral-mini-3b-2507", "Mistral Voxtral Mini 3B — ~$0.06/h"),
)

# Chat models suggested for summarize / clean-up (any OpenRouter id is accepted).
CHAT_MODELS: tuple[str, ...] = (
    "google/gemini-2.5-flash-lite",
    "openai/gpt-4o-mini",
    "mistralai/mistral-small-3.2-24b-instruct",
)

_SUMMARIZE_PROMPT = (
    "Summarize the following note in 1-3 concise sentences. Return only the summary, no preamble."
)
_CLEAN_PROMPT = (
    "Clean up the following note: fix spelling, grammar and formatting, "
    "preserve meaning and any URLs. Return only the cleaned text."
)


class OpenRouterError(Exception):
    """Raised when an OpenRouter request fails or no key is configured."""


# ---- key management -------------------------------------------------------


def get_api_key() -> str | None:
    env = os.environ.get("OPENROUTER_API_KEY")
    if env:
        return env
    try:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        return None


def set_api_key(key: str) -> None:
    import keyring

    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key)


def clear_api_key() -> None:
    try:
        import keyring

        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        pass


def has_api_key() -> bool:
    """True only when a plausibly-valid key is configured.

    Guards against a placeholder/garbage string enabling the AI buttons — a
    real OpenRouter key starts with 'sk-or-'. An env-provided key is trusted
    as-is (power users may use a proxy), but keyring values are format-checked.
    """
    import os

    if os.environ.get("OPENROUTER_API_KEY"):
        return True
    key = get_api_key()
    return is_valid_key_format(key)


def is_valid_key_format(key: str | None) -> bool:
    return bool(key and key.startswith("sk-or-") and len(key) > 20)


# ---- client ---------------------------------------------------------------


class OpenRouterClient:
    def __init__(self, model: str, timeout: float = 30.0) -> None:
        self.model = model
        self.timeout = timeout

    def summarize(self, text: str) -> str:
        return self._complete(_SUMMARIZE_PROMPT, text)

    def clean(self, text: str) -> str:
        return self._complete(_CLEAN_PROMPT, text)

    def _complete(self, system_prompt: str, text: str) -> str:
        key = get_api_key()
        if not key:
            raise OpenRouterError("No OpenRouter API key configured.")
        if not text.strip():
            raise OpenRouterError("Nothing to process (empty text).")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        }
        headers = {"Authorization": f"Bearer {key}", **_HEADERS}
        try:
            resp = httpx.post(_API_URL, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as exc:
            raise OpenRouterError(
                f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc


# ---- speech-to-text -------------------------------------------------------


def wav_bytes(audio, sample_rate: int) -> bytes:
    """Encode float32 mono samples in [-1, 1] as 16-bit PCM WAV."""
    import io
    import wave

    import numpy as np

    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


def transcribe(audio, sample_rate: int, model: str, language: str, timeout: float = 70.0) -> str:
    """Transcribe audio with an OpenRouter speech-to-text model.

    Keep clips under ~60 s of processing: upstream providers time out after
    60 seconds per request (the live transcript already sends ≤25 s chunks).
    """
    import base64

    key = get_api_key()
    if not key:
        raise OpenRouterError("No OpenRouter API key configured (Settings → Integrations).")
    payload: dict = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(wav_bytes(audio, sample_rate)).decode("ascii"),
            "format": "wav",
        },
    }
    if language and language != "auto":
        payload["language"] = language
    headers = {"Authorization": f"Bearer {key}", **_HEADERS}
    try:
        resp = httpx.post(_STT_URL, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return str(resp.json().get("text", "")).strip()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterError(
            f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OpenRouterError(f"OpenRouter transcription failed: {exc}") from exc
