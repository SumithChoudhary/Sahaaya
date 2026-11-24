from __future__ import annotations

import os
import csv
import io
import json
from typing import Any

from .base import FetchResult, NormalizedRecord, ProviderNotConfigured


class CWCConnector:
    """CWC adapter deliberately requires a verified authorized feed URL."""
    source_key = "cwc_flood_forecast"

    def _url(self, source: Any) -> str:
        return os.getenv("CWC_FLOOD_FEED_URL", "").strip() or str(source.endpoint or "").strip()

    def is_configured(self, source: Any) -> bool:
        return bool(self._url(source))

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        if not self.is_configured(source):
            raise ProviderNotConfigured("No verified public CWC API endpoint is configured. Supply an authorized feed or import a verified dataset.")
        from .http import get_response
        response = await get_response(self._url(source), allowed_hosts={"ffs.india-water.gov.in", "aff.india-water.gov.in", "inf.cwc.gov.in"}, headers={"If-None-Match": etag} if etag else None)
        if response.status_code == 304:
            return FetchResult(etag=etag, not_modified=True, message="CWC resource has not changed")
        content_type = response.headers.get("Content-Type", "").lower()
        if "csv" in content_type or self._url(source).lower().endswith(".csv"):
            try:
                rows = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
                records = [NormalizedRecord(kind="raw", external_id=str(row.get("id") or row.get("ID") or f"row:{index + 1}"), raw=dict(row), values={}, source_url=self._url(source)) for index, row in enumerate(rows)]
            except (UnicodeDecodeError, csv.Error) as exc:
                raise RuntimeError("CWC resource is not a readable UTF-8 CSV") from exc
        else:
            try:
                payload = json.loads(response.content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError(f"CWC resource content type {content_type or 'unknown'} has no configured parser") from exc
            rows = payload.get("features", []) if isinstance(payload, dict) and payload.get("type") == "FeatureCollection" else payload if isinstance(payload, list) else [payload]
            records = [NormalizedRecord(kind="raw", external_id=str(row.get("id") or row.get("ID") or f"row:{index + 1}"), raw=row, values={}, source_url=self._url(source)) for index, row in enumerate(rows) if isinstance(row, dict)]
        return FetchResult(records=records, etag=response.headers.get("ETag"), message="CWC response preserved as raw records pending a reviewed schema mapping")
