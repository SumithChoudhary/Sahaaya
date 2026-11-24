from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 12 * 1024 * 1024


class ProviderResponse:
    def __init__(self, status_code: int, headers, content: bytes):
        self.status_code, self.headers, self.content = status_code, headers, content

    def json(self):
        return json.loads(self.content)


class _SameHostHTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        original, target = urlsplit(request.full_url), urlsplit(new_url)
        if target.scheme.lower() != "https" or target.hostname != original.hostname:
            raise URLError("Provider redirect must remain HTTPS on the same host")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, timezone.utc)
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _request(url: str, headers: dict[str, str], timeout_seconds: float) -> ProviderResponse:
    request = Request(url, headers=headers, method="GET")
    try:
        with build_opener(_SameHostHTTPSRedirect()).open(request, timeout=timeout_seconds) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("Provider response exceeds the configured 12 MB limit")
            return ProviderResponse(response.status, response.headers, content)
    except HTTPError as response:
        if response.code == 304:
            return ProviderResponse(304, response.headers, b"")
        return ProviderResponse(response.code, response.headers, response.read(MAX_RESPONSE_BYTES + 1))


async def get_response(url: str, *, allowed_hosts: set[str], headers: dict[str, str] | None = None, params: dict[str, Any] | None = None,
                       timeout_seconds: float = 12, retries: int = 2) -> ProviderResponse:
    """GET only from an approved HTTPS provider host, with bounded size/retries."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme.lower() != "https" or parsed_url.hostname not in allowed_hosts or parsed_url.username or parsed_url.password:
        raise RuntimeError("Provider URL must use HTTPS on its approved host and must not contain embedded credentials")
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params, doseq=True)}"
    request_headers = {"User-Agent": "Sahaaya-Decision-Support/1.0", "Accept": "application/json, application/geo+json, application/xml, text/csv, */*", **(headers or {})}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await asyncio.to_thread(_request, url, request_headers, timeout_seconds)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = response.headers.get("Retry-After", "")
                delay = min(float(retry_after), 3.0) if retry_after.isdigit() else 0.25 * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            if response.status_code >= 400 and response.status_code != 304:
                raise RuntimeError(f"Provider returned HTTP {response.status_code}")
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ValueError("Provider response exceeds the configured 12 MB limit")
            return response
        except (TimeoutError, URLError, OSError, RuntimeError, ValueError) as exc:
            last_error = exc
            if isinstance(exc, RuntimeError) and "HTTP" in str(exc) and not any(code in str(exc) for code in ("429", "500", "502", "503", "504")):
                break
            if isinstance(exc, ValueError) and "12 MB" in str(exc):
                break
            if attempt < retries:
                await asyncio.sleep(0.25 * (2 ** attempt))
    raise RuntimeError(f"Provider request failed: {str(last_error)[:300]}" if last_error else "Provider request failed") from last_error


def validate_coordinates(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon
