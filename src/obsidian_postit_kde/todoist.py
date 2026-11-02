"""Todoist Quick Add integration for explicitly marked diary tasks."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import APP_ID

_KEYRING_USER = "todoist_api_token"
_TASKS_URL = "https://api.todoist.com/api/v1/tasks"
_PROJECTS_URL = "https://api.todoist.com/api/v1/projects"
_TASK_PREFIX = re.compile(r"^todo:\s*(.*)$", re.IGNORECASE | re.DOTALL)
_METADATA = re.compile(r"(?<!\S)(?P<kind>[@#])(?P<name>[\w-]+)(?=\s|$)")
_PRIORITY = re.compile(r"(?<!\S)p([1-4])(?=\s|$)", re.IGNORECASE)
_DUE = re.compile(
    r"\b(today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))"
    r"(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?$",
    re.IGNORECASE,
)


class TodoistError(Exception):
    """Raised when a Todoist task cannot be created."""


@dataclass(frozen=True)
class TaskFields:
    content: str
    due_string: str | None = None
    priority: int | None = None
    labels: tuple[str, ...] = ()
    project: str | None = None
    description: str | None = None


def parse_diary_task(entry: str) -> str | None:
    """Return Quick Add text for a `todo:` diary entry, or None otherwise."""
    match = _TASK_PREFIX.fullmatch(entry.strip())
    if match is None:
        return None
    task = " ".join(match.group(1).split())
    if not task:
        raise TodoistError("Add a task after 'todo:'.")
    return task


def parse_task_fields(task: str) -> TaskFields:
    """Parse a small, explicit subset of Todoist's quick-entry syntax."""
    text, separator, description = task.partition(" // ")
    projects: list[str] = []
    labels: list[str] = []

    def metadata(match: re.Match[str]) -> str:
        (projects if match.group("kind") == "#" else labels).append(match.group("name"))
        return ""

    text = _METADATA.sub(metadata, text)
    priorities = _PRIORITY.findall(text)
    text = _PRIORITY.sub("", text)
    text = " ".join(text.split())
    due = _DUE.search(text)
    due_string = due.group(0).strip() if due else None
    content = text[: due.start()].strip() if due else text
    if not content:
        raise TodoistError("The Todoist task needs a title.")
    if len(projects) > 1:
        raise TodoistError("Use only one #project in a Todoist task.")
    return TaskFields(
        content=content,
        due_string=due_string,
        priority=int(priorities[-1]) if priorities else None,
        labels=tuple(labels),
        project=projects[0] if projects else None,
        description=description.strip() if separator else None,
    )


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


def create_task(task: str, timeout: float = 30.0) -> str:
    """Create a task and return its task-specific Todoist web URL."""
    token = get_api_token()
    if not token:
        raise TodoistError("Add a Todoist API token in Settings first.")
    fields = parse_task_fields(task)
    headers = {"Authorization": f"Bearer {token}"}
    payload: dict[str, object] = {"content": fields.content}
    if fields.due_string:
        payload["due_string"] = fields.due_string
    if fields.priority:
        payload["priority"] = fields.priority
    if fields.labels:
        payload["labels"] = list(fields.labels)
    if fields.description:
        payload["description"] = fields.description
    try:
        if fields.project:
            cursor = None
            project = None
            while True:
                projects_response = httpx.get(
                    _PROJECTS_URL,
                    headers=headers,
                    timeout=timeout,
                    params={"cursor": cursor} if cursor else None,
                )
                projects_response.raise_for_status()
                page = projects_response.json()
                project = next(
                    (
                        p
                        for p in page.get("results", [])
                        if p.get("name", "").casefold() == fields.project.casefold()
                    ),
                    None,
                )
                cursor = page.get("next_cursor")
                if project is not None or not cursor:
                    break
            if project is None:
                raise TodoistError(f"Todoist project #{fields.project} was not found.")
            payload["project_id"] = project["id"]
        response = httpx.post(
            _TASKS_URL,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        task_id = str(data["id"])
        if not re.fullmatch(r"[A-Za-z0-9]+", task_id):
            raise TodoistError("Todoist returned an invalid task ID.")
        canonical = data.get("url", "")
        parsed = urlparse(canonical)
        if parsed.scheme == "https" and parsed.hostname in {"todoist.com", "app.todoist.com"}:
            return canonical
        return f"https://app.todoist.com/app/task/{task_id}"
    except httpx.HTTPStatusError as exc:
        raise TodoistError(f"Todoist returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise TodoistError(f"Todoist request failed: {exc}") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise TodoistError("Todoist returned an invalid task response.") from exc
