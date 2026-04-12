"""Shared HTTP helpers for Motis search engines."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from motis_data_mcp.providers.safety import ensure_safe_public_url, redirect_guard

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
}


async def request_text(
    url: str,
    *,
    method: str = "GET",
    params: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | str | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 20.0,
) -> str:
    ensure_safe_public_url(url)

    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient(
        event_hooks={"response": [redirect_guard]},
        follow_redirects=True,
        headers=request_headers,
        timeout=timeout_seconds,
        trust_env=False,
    ) as client:
        response = await client.request(
            method=method,
            url=url,
            params=params,
            data=data,
        )
        response.raise_for_status()
        return response.text
