from __future__ import annotations

import json
import os
from typing import Any

from .base import FetchResult, NormalizedRecord, ProviderNotConfigured
from .http import get_response, parse_datetime


class IMDConnector:
    """IMD adapter requiring operator-supplied endpoints and documented auth headers.

    The public reference lists endpoints and schemas but does not specify a
    request-authentication header format. Sahaaya therefore does not guess one.
    """
    source_key = "imd_weather"

    def _config(self) -> tuple[dict[str, str], dict[str, str]]:
        try:
            endpoints = json.loads(os.getenv("IMD_ENDPOINTS_JSON", "{}"))
            headers = json.loads(os.getenv("IMD_AUTH_HEADERS_JSON", "{}"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("IMD endpoint/header configuration must be valid JSON") from exc
        if not isinstance(endpoints, dict) or not isinstance(headers, dict):
            raise RuntimeError("IMD endpoint/header configuration must be JSON objects")
        return ({str(k): str(v) for k, v in endpoints.items()}, {str(k): str(v) for k, v in headers.items()})

    def is_configured(self, source: Any) -> bool:
        endpoints, headers = self._config()
        return bool(endpoints and headers)

    async def fetch(self, source: Any, etag: str | None = None) -> FetchResult:
        endpoints, headers = self._config()
        if not endpoints or not headers:
            raise ProviderNotConfigured("IMD requires authorized API access and its documented authentication details; configure endpoints and headers from the issued access instructions.")
        # Endpoint URLs and auth are supplied by the operator based on IMD's
        # current account-specific documentation; no auth scheme is assumed.
        records: list[NormalizedRecord] = []
        for endpoint_name, url in endpoints.items():
            response = await get_response(url, allowed_hosts={"api.imd.gov.in"}, headers=headers)
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError(f"IMD endpoint {endpoint_name} returned invalid JSON") from exc
            rows = payload if isinstance(payload, list) else payload.get("data", [payload]) if isinstance(payload, dict) else []
            if isinstance(rows, dict):
                rows = [rows]
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                external_id = str(row.get("ID") or row.get("OBJ_ID") or row.get("Station Id") or row.get("Station") or f"{endpoint_name}:{index}")
                observed = parse_datetime(row.get("Date of Observation") or row.get("DATE") or row.get("Date") or row.get("date_obs"))
                if observed is None:
                    continue
                known = [("temperature", "Temperature", "degC"), ("rainfall_24h", "Last 24 hrs Rainfall", "mm"),
                         ("wind_speed", "Wind Speed", "km/h"), ("humidity", "Humidity", "%"),
                         ("rainfall", "Rainfall", "mm")]
                for variable, source_field, unit in known:
                    raw_value = row.get(source_field)
                    if raw_value in (None, ""):
                        continue
                    try:
                        value = float(str(raw_value).replace(",", ""))
                    except ValueError:
                        continue
                    records.append(NormalizedRecord(kind="weather", external_id=f"{endpoint_name}:{external_id}:{variable}:{observed.isoformat()}", raw=row,
                        values={"variable": variable, "value": value, "unit": unit, "observed_at": observed,
                                "latitude": row.get("Latitude") or row.get("latitude"), "longitude": row.get("Longitude") or row.get("longitude"),
                                "quality_status": "unreviewed"}, published_at=observed, source_url=url))
        return FetchResult(records=records, message="Configured IMD endpoints fetched; provider fields retained with provenance")
