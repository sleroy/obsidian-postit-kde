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
        headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://github.com/sleroy/obsidian-postit-kde",
            "X-Title": "obsidian-postit-kde",
        }
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
