"""Todoist Quick Add integration for explicitly marked diary tasks."""

from __future__ import annotations

import os
import re

import httpx

from .config import APP_ID

_KEYRING_USER = "todoist_api_token"
_QUICK_ADD_URL = "https://api.todoist.com/api/v1/tasks/quick"
_TASK_PREFIX = re.compile(r"^todo:\s*(.*)$", re.IGNORECASE | re.DOTALL)


class TodoistError(Exception):
    """Raised when a Todoist task cannot be created."""


def parse_diary_task(entry: str) -> str | None:
    """Return Quick Add text for a `todo:` diary entry, or None otherwise."""
    match = _TASK_PREFIX.fullmatch(entry.strip())
    if match is None:
        return None
    task = " ".join(match.group(1).split())
    if not task:
        raise TodoistError("Add a task after 'todo:'.")
    return task


def get_api_token() -> str | None:
    env = os.environ.get("TODOIST_API_TOKEN")
    if env:
        return env
    try:
        import keyring

        return keyring.get_password(APP_ID, _KEYRING_USER)
    except Exception:
        return None


def set_api_token(token: str) -> None:
    import keyring

    keyring.set_password(APP_ID, _KEYRING_USER, token)


def has_api_token() -> bool:
    return bool(get_api_token())


def quick_add(task: str, timeout: float = 30.0) -> None:
    token = get_api_token()
    if not token:
        raise TodoistError("Add a Todoist API token in Settings first.")
    try:
        response = httpx.post(
            _QUICK_ADD_URL,
            json={"text": task},
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TodoistError(f"Todoist returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise TodoistError(f"Todoist request failed: {exc}") from exc
