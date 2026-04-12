"""HTTP-backed URL extraction provider for Motis Data MCP."""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser

import httpx

from motis_data_mcp.contracts import (
    ToolEnvelope,
    WebDocument,
    WebExtractPayload,
    WebExtractRequest,
    build_tool_envelope,
    payload_dict,
)
from motis_data_mcp.providers.safety import ensure_safe_public_url, redirect_guard

_DEFAULT_TIMEOUT = 30.0
_USER_AGENT = (
    "MotisDataMCP/0.1 (+https://github.com/DaddyElonMusk69/motis; "
    "read-only networking boundary)"
)
_TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/ld+json",
    "application/xml",
    "application/xhtml+xml",
)
_MAX_DOWNLOAD_BYTES = 2_000_000


class _HTMLToMarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_stack: list[str] = []
        self._link_stack: list[str | None] = []
        self._list_depth = 0
        self.title: str | None = None
        self._capturing_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            self._skip_stack.append(lowered)
            return
        if self._skip_stack:
            return
        if lowered == "title":
            self._capturing_title = True
        elif lowered in {"br"}:
            self._chunks.append("\n")
        elif lowered in {"p", "div", "section", "article", "header", "footer", "main"}:
            self._chunks.append("\n\n")
        elif lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(lowered[1])
            self._chunks.append(f"\n\n{'#' * level} ")
        elif lowered in {"ul", "ol"}:
            self._list_depth += 1
            self._chunks.append("\n")
        elif lowered == "li":
            indent = "  " * max(self._list_depth - 1, 0)
            self._chunks.append(f"\n{indent}- ")
        elif lowered == "a":
            self._link_stack.append(attrs_dict.get("href"))
        elif lowered == "pre":
            self._chunks.append("\n\n```\n")
        elif lowered == "code":
            self._chunks.append("`")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._skip_stack:
            if lowered == self._skip_stack[-1]:
                self._skip_stack.pop()
            return
        if lowered == "title":
            self._capturing_title = False
        elif lowered in {"ul", "ol"} and self._list_depth > 0:
            self._list_depth -= 1
            self._chunks.append("\n")
        elif lowered == "a" and self._link_stack:
            href = self._link_stack.pop()
            if href:
                self._chunks.append(f" ({href})")
        elif lowered == "pre":
            self._chunks.append("\n```\n")
        elif lowered == "code":
            self._chunks.append("`")
        elif lowered in {"p", "div", "section", "article", "header", "footer", "main"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = data.strip()
        if not text:
            return
        if self._capturing_title and not self.title:
            self.title = text
        self._chunks.append(text)

    def markdown(self) -> str:
        text = "".join(self._chunks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        return text.strip()


def _looks_textual(content_type: str) -> bool:
    lowered = content_type.lower()
    return any(token in lowered for token in _TEXTUAL_CONTENT_TYPES)


def _extract_meta_value(html: str, *patterns: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return unescape(match.group(1)).strip()
    return None


def _normalize_plain_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _markdown_to_text(text: str) -> str:
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("```", "")
    text = text.replace("`", "")
    text = re.sub(r"\s+\((https?://[^)]+)\)", "", text)
    return _normalize_plain_text(text)


def _truncate(text: str, limit: int | None) -> tuple[str, bool]:
    if limit is None or len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "\n\n[truncated]", True


def _render_json_text(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)


def _html_to_document(url: str, final_url: str, html: str, content_type: str, status_code: int, max_chars: int | None) -> tuple[WebDocument, bool]:
    parser = _HTMLToMarkdownParser()
    parser.feed(html)
    parser.close()

    title = parser.title or _extract_meta_value(
        html,
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
    )
    excerpt = _extract_meta_value(
        html,
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    )
    published_at = _extract_meta_value(
        html,
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
    )
    markdown = parser.markdown()
    content, truncated = _truncate(markdown, max_chars)

    return (
        WebDocument(
            url=url,
            final_url=final_url,
            title=title,
            source=final_url,
            content_type=content_type,
            status_code=status_code,
            excerpt=excerpt or (content[:280] if content else None),
            content=content,
            published_at=published_at,
            metadata={"truncated": truncated, "parser": "html_to_markdown"},
        ),
        truncated,
    )


def _html_as_text_document(url: str, final_url: str, html: str, content_type: str, status_code: int, max_chars: int | None) -> tuple[WebDocument, bool]:
    markdown_document, _ = _html_to_document(url, final_url, html, content_type, status_code, None)
    plain_text = _markdown_to_text(markdown_document.content or "")
    content, truncated = _truncate(plain_text, max_chars)
    markdown_document.content = content
    markdown_document.excerpt = markdown_document.excerpt or (content[:280] if content else None)
    markdown_document.metadata = {"truncated": truncated, "parser": "html_to_text"}
    return markdown_document, truncated


def _html_raw_document(url: str, final_url: str, html: str, content_type: str, status_code: int, max_chars: int | None) -> tuple[WebDocument, bool]:
    title = _extract_meta_value(
        html,
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
    )
    excerpt = _extract_meta_value(
        html,
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    )
    content, truncated = _truncate(html, max_chars)
    return (
        WebDocument(
            url=url,
            final_url=final_url,
            title=title,
            source=final_url,
            content_type=content_type,
            status_code=status_code,
            excerpt=excerpt or (content[:280] if content else None),
            content=content,
            metadata={"truncated": truncated, "parser": "raw_html"},
        ),
        truncated,
    )


def _text_to_document(url: str, final_url: str, body: str, content_type: str, status_code: int, max_chars: int | None) -> tuple[WebDocument, bool]:
    normalized = _normalize_plain_text(body)
    content, truncated = _truncate(normalized, max_chars)
    return (
        WebDocument(
            url=url,
            final_url=final_url,
            source=final_url,
            content_type=content_type,
            status_code=status_code,
            excerpt=content[:280] if content else None,
            content=content,
            metadata={"truncated": truncated, "parser": "plain_text"},
        ),
        truncated,
    )


def _json_to_document(url: str, final_url: str, body: str, content_type: str, status_code: int, max_chars: int | None) -> tuple[WebDocument, bool]:
    rendered = _render_json_text(body)
    content, truncated = _truncate(rendered, max_chars)
    return (
        WebDocument(
            url=url,
            final_url=final_url,
            source=final_url,
            content_type=content_type,
            status_code=status_code,
            excerpt=content[:280] if content else None,
            content=content,
            metadata={"truncated": truncated, "parser": "json"},
        ),
        truncated,
    )


class HTTPReaderProvider:
    name = "http_reader"

    async def extract(self, request: WebExtractRequest, *, tool_name: str) -> ToolEnvelope:
        warnings: list[str] = []
        documents: list[WebDocument] = []

        async with httpx.AsyncClient(
            timeout=min(float(request.timeout_seconds), _DEFAULT_TIMEOUT),
            follow_redirects=True,
            event_hooks={"response": [redirect_guard]},
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
            },
        ) as client:
            for url in request.urls:
                try:
                    ensure_safe_public_url(url)
                    response = await client.get(url)
                    response.raise_for_status()
                    final_url = str(response.url)
                    ensure_safe_public_url(final_url)

                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    content_length = len(response.content)
                    if content_length > _MAX_DOWNLOAD_BYTES:
                        raise ValueError(f"Response exceeded {_MAX_DOWNLOAD_BYTES} bytes")
                    if not _looks_textual(content_type):
                        raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")

                    body = response.text
                    if content_type == "application/json" or request.format == "json":
                        document, truncated = _json_to_document(
                            url,
                            final_url,
                            body,
                            content_type,
                            response.status_code,
                            request.max_chars_per_url,
                        )
                    elif "html" in content_type:
                        if request.format == "html":
                            document, truncated = _html_raw_document(
                                url,
                                final_url,
                                body,
                                content_type,
                                response.status_code,
                                request.max_chars_per_url,
                            )
                        elif request.format == "text":
                            document, truncated = _html_as_text_document(
                                url,
                                final_url,
                                body,
                                content_type,
                                response.status_code,
                                request.max_chars_per_url,
                            )
                        else:
                            document, truncated = _html_to_document(
                                url,
                                final_url,
                                body,
                                content_type,
                                response.status_code,
                                request.max_chars_per_url,
                            )
                    else:
                        document, truncated = _text_to_document(
                            url,
                            final_url,
                            body,
                            content_type,
                            response.status_code,
                            request.max_chars_per_url,
                        )
                    if truncated:
                        warnings.append(f"Truncated content for {final_url}")
                    documents.append(document)
                except Exception as exc:
                    warnings.append(f"Failed to read {url}: {exc}")
                    documents.append(
                        WebDocument(
                            url=url,
                            source=url,
                            excerpt=None,
                            content=None,
                            metadata={"error": str(exc)},
                        )
                    )

        return build_tool_envelope(
            tool=tool_name,
            provider=self.name,
            warnings=warnings,
            data=payload_dict(WebExtractPayload(documents=documents)),
        )
