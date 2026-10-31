"""Fetch a URL and turn it into Markdown for storing in the diary / a note.

Uses httpx (already a dependency) to fetch, and markdownify when available for
a faithful HTML->Markdown conversion; otherwise falls back to a small stdlib
HTML-to-text extractor. Returns a (title, markdown) pair.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

import httpx


class WebClipError(Exception):
    """Raised when a URL cannot be fetched or parsed."""


def fetch_markdown(url: str, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch `url` and return (title, markdown_body)."""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise WebClipError(f"Not an http(s) URL: {url!r}")
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "obsidian-postit-kde/0.1 (+webclip)"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise WebClipError(f"Could not fetch {url}: {exc}") from exc

    ctype = resp.headers.get("content-type", "")
    text = resp.text
    if "html" not in ctype and not text.lstrip().lower().startswith("<!doctype html"):
        # Treat non-HTML (e.g. text/markdown, text/plain) as-is.
        return (url, text.strip())

    title = _extract_title(text) or url
    body = _html_to_markdown(text)
    return (title, body)


def _extract_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else ""


def _html_to_markdown(html_text: str) -> str:
    try:
        from markdownify import markdownify as md  # type: ignore

        out = md(html_text, heading_style="ATX", strip=["script", "style"])
        return _collapse_blank_lines(out.strip())
    except ModuleNotFoundError:
        return _stdlib_html_to_text(html_text)


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


class _TextExtractor(HTMLParser):
    """Minimal fallback: strip tags to readable text, keeping paragraph breaks."""

    _SKIP = {"script", "style", "head", "noscript", "svg"}
    _BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._parts.append("\n")
        if tag in ("h1", "h2", "h3"):
            self._parts.append("## ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data.strip() + " ")

    def text(self) -> str:
        return _collapse_blank_lines("".join(self._parts)).strip()


def _stdlib_html_to_text(html_text: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_text)
    return parser.text()
