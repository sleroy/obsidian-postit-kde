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


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def detect_bare_url(entry: str) -> tuple[str, str] | None:
    """If `entry` is *only* a URL (plus optional #tags), return (url, tags).

    Returns None when the entry contains other words, more than one URL, or no
    URL — so 'interesting url http://x' stays plain text while 'http://x #read'
    is recognised as a clip. `tags` is a space-separated string (may be empty).
    """
    stripped = entry.strip()
    if not stripped:
        return None
    tokens = stripped.split()
    urls = [t for t in tokens if _URL_RE.fullmatch(t)]
    tags = [t for t in tokens if t.startswith("#") and len(t) > 1]
    # Every token must be either the single URL or a #tag — nothing else.
    if len(urls) != 1:
        return None
    if len(urls) + len(tags) != len(tokens):
        return None
    tag_str = " ".join(t.lstrip("#") for t in tags)
    return urls[0].rstrip(".,);]'\"”’"), tag_str


def _is_blocked_host(host: str) -> bool:
    """True if `host` resolves to a loopback/private/link-local/reserved address."""
    import ipaddress
    import socket

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable → refuse
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return True
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


_MAX_BYTES = 8 * 1024 * 1024  # 8 MB cap to avoid OOM on hostile responses
_MAX_REDIRECTS = 5


def fetch_markdown(url: str, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch `url` and return (title, markdown_body).

    Hardened against SSRF: rejects URLs resolving to internal/loopback/private
    addresses, validates every redirect hop, and caps the response size.
    """
    import urllib.parse

    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise WebClipError(f"Not an http(s) URL: {url!r}")

    headers = {"User-Agent": "obsidian-postit-kde/0.1 (+webclip)"}
    current = url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                host = urllib.parse.urlparse(current).hostname or ""
                if _is_blocked_host(host):
                    raise WebClipError(f"Refusing to fetch an internal/loopback address: {host}")
                resp = client.get(current, headers=headers)
                if resp.is_redirect:
                    loc = resp.headers.get("location", "")
                    current = urllib.parse.urljoin(current, loc)
                    if not re.match(r"^https?://", current, re.IGNORECASE):
                        raise WebClipError(f"Refusing non-http(s) redirect to {current!r}")
                    continue
                resp.raise_for_status()
                break
            else:
                raise WebClipError("Too many redirects.")
    except httpx.HTTPError as exc:
        raise WebClipError(f"Could not fetch {url}: {exc}") from exc

    clen = resp.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > _MAX_BYTES:
        raise WebClipError("Response too large to clip.")
    raw = resp.content[:_MAX_BYTES]
    text = raw.decode(resp.encoding or "utf-8", errors="replace")

    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and not text.lstrip().lower().startswith("<!doctype html"):
        return (url, text.strip())

    title = _extract_title(text) or url
    body = _html_to_markdown(text)
    return (title, body)


def _extract_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else ""


def _isolate_main(html_text: str) -> str:
    """Return the main article region of a page, dropping chrome.

    Prefers <article>, then <main>, then an element with role="main"; falls
    back to the full document. This removes most nav/menu/footer boilerplate
    before conversion so the clip focuses on the actual content.
    """
    for pattern in (
        r"<article\b[^>]*>(.*?)</article>",
        r"<main\b[^>]*>(.*?)</main>",
        r'<[^>]+\brole=["\']main["\'][^>]*>(.*?)</[a-zA-Z]+>',
    ):
        matches = re.findall(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if matches:
            # Pick the largest matching region (the real content, not a teaser).
            return max(matches, key=len)
    return html_text


def _strip_chrome(html_text: str) -> str:
    """Remove non-content elements entirely (with their contents)."""
    for tag in (
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
        "template",
        "iframe",
    ):
        html_text = re.sub(
            rf"<{tag}\b[^>]*>.*?</{tag}>", " ", html_text, flags=re.IGNORECASE | re.DOTALL
        )
    return html_text


def _html_to_markdown(html_text: str) -> str:
    content = _strip_chrome(_isolate_main(html_text))
    try:
        from markdownify import markdownify as md  # type: ignore

        out = md(content, heading_style="ATX", strip=["script", "style"])
        return _collapse_blank_lines(out.strip())
    except ModuleNotFoundError:
        return _stdlib_html_to_text(content)


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


class _TextExtractor(HTMLParser):
    """Minimal fallback: strip tags to readable text, keeping paragraph breaks."""

    _SKIP = {
        "script",
        "style",
        "head",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
        "template",
        "iframe",
    }
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
