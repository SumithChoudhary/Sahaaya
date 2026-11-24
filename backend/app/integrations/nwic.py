from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Any

from .base import FetchResult, NormalizedRecord, ProviderNotConfigured
from .http import get_response, parse_datetime, validate_coordinates


class NWICRainfallConnector:
    """Consumes an operator-configured NWIC resource download; no guessed API path."""
    source_key = "nwic_telangana_rainfall"

    def _url(self, source: Any) -> str:
        return os.getenv("NWIC_TELANGANA_RAINFALL_URL", "").strip() or str(source.endpoint or "").strip()

    def is_configured(self, source: Any) -> bool:
        return bool(self._url(source))

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        url = self._url(source)
        if not url:
            raise ProviderNotConfigured("Configure an authorized NWIC Telangana rainfall CSV/resource URL after confirming its resource and schema.")
        response = await get_response(url, allowed_hosts={"nwdp.nwic.gov.in", "www.nwdp.nwic.gov.in"}, headers={"If-None-Match": etag} if etag else None)
        if response.status_code == 304:
            return FetchResult(etag=etag, not_modified=True, message="NWIC resource has not changed")
        try:
            text = response.content.decode("utf-8-sig")
            rows = csv.DictReader(io.StringIO(text))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise RuntimeError("NWIC resource is not a readable UTF-8 CSV") from exc
        # Preserve each row verbatim first. Normalize rainfall only when a known
        # mapping is present; do not infer incompatible units/columns silently.
        mapping = source.config.get("column_mapping", {}) if isinstance(source.config, dict) else {}
        records = []
        for index, row in enumerate(rows):
            external_id = str(row.get(mapping.get("id")) if mapping.get("id") else "") or f"row:{index + 1}"
            values: dict[str, Any] = {"quality_status": "unreviewed"}
            timestamp_col = mapping.get("observed_at")
            value_col = mapping.get("value")
            unit = mapping.get("unit")
            lat_col, lon_col = mapping.get("latitude"), mapping.get("longitude")
            station_col = mapping.get("station") or mapping.get("station_name")
            state_col, state_code_col = mapping.get("state"), mapping.get("state_code")
            district_col, district_code_col = mapping.get("district"), mapping.get("district_code")
            if timestamp_col and value_col and unit and timestamp_col in row and value_col in row:
                observed = parse_datetime(row.get(timestamp_col))
                try:
                    rainfall = float(row[value_col])
                except (ValueError, TypeError):
                    rainfall = None
                if observed and rainfall is not None and observed <= datetime.now(timezone.utc):
                    location = validate_coordinates(row.get(lat_col), row.get(lon_col)) if lat_col and lon_col else None
                    values.update({"variable": mapping.get("variable", "rainfall"), "value": rainfall, "unit": str(unit),
                                   "observed_at": observed, "latitude": location[0] if location else None,
                                   "longitude": location[1] if location else None,
                                   "location_name": row.get(station_col) if station_col else None,
                                   "state_name": row.get(state_col) if state_col else None,
                                   "state_code": row.get(state_code_col) if state_code_col else None,
                                   "district_name": row.get(district_col) if district_col else None,
                                   "district_code": row.get(district_code_col) if district_code_col else None})
            records.append(NormalizedRecord(kind="weather" if "observed_at" in values else "raw", external_id=external_id,
                raw=dict(row), values=values, published_at=values.get("observed_at"), source_url=url))
        return FetchResult(records=records, etag=response.headers.get("ETag"), message="NWIC resource fetched; rows without an approved column mapping remain raw")
